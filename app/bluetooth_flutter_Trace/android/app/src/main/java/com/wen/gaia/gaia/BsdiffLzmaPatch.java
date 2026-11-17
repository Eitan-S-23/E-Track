package com.wen.gaia.gaia;

import java.io.BufferedInputStream;
import java.io.EOFException;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.RandomAccessFile;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Arrays;
import java.util.concurrent.CancellationException;
import java.util.zip.CRC32;
import org.tukaani.xz.LZMAInputStream;

/** The MCU encoder's interleaved bsdiff stream, without ETU or AES packaging. */
public final class BsdiffLzmaPatch {
    public static final String FORMAT = "bsdiff-lzma-v1";
    public static final int CHUNK = 64 * 1024;
    public static final long MAX_FILE = 256L * 1024 * 1024;
    public static final int MAX_DICTIONARY = 8 * 1024 * 1024;
    public static final int MAX_CONTROLS = 1_000_000;
    private static final long TIMEOUT_NANOS = 120_000_000_000L;

    public interface Observer {
        boolean cancelled();
        void progress(long completed, long total);
    }

    public static final class Result {
        public final long bytes;
        public final long elapsedMillis;
        public final int dictionaryBytes;
        public final int controls;

        Result(long bytes, long elapsedMillis, int dictionaryBytes, int controls) {
            this.bytes = bytes;
            this.elapsedMillis = elapsedMillis;
            this.dictionaryBytes = dictionaryBytes;
            this.controls = controls;
        }
    }

    private BsdiffLzmaPatch() {}

    public static Result apply(File base, File patch, File output, String baseSha,
            String patchSha, String targetSha, long targetSize, Observer observer) throws IOException {
        require(baseSha.matches("[0-9a-f]{64}") && patchSha.matches("[0-9a-f]{64}")
                && targetSha.matches("[0-9a-f]{64}"), "Invalid SHA-256 identity");
        require(targetSize > 0 && targetSize <= MAX_FILE, "Output exceeds limit");
        require(base.isFile() && base.length() > 0 && base.length() <= MAX_FILE, "Invalid base size");
        require(patch.isFile() && patch.length() > 40 && patch.length() <= MAX_FILE, "Invalid patch size");
        require(!output.exists() && !output.getCanonicalFile().equals(base.getCanonicalFile())
                && !output.getCanonicalFile().equals(patch.getCanonicalFile()), "Output already exists or aliases input");
        final long started = System.nanoTime();
        checkpoint(observer, started);
        byte[] buffer = new byte[CHUNK];
        require(hash(patch, buffer, observer, started).equals(patchSha), "Patch SHA-256 mismatch");

        boolean created = false;
        boolean success = false;
        try (RandomAccessFile old = new RandomAccessFile(base, "r");
                InputStream compressed = new BufferedInputStream(new FileInputStream(patch), CHUNK)) {
            byte[] header = new byte[40];
            exact(compressed, header, 0, header.length);
            long headerCrc = u32(header, 0, false);
            Arrays.fill(header, 0, 4, (byte) 0);
            CRC32 crc = new CRC32();
            crc.update(header);
            require(crc.getValue() == headerCrc, "Header CRC mismatch");
            require(u32(header, 4, false) == patch.length() - 40, "Compressed length mismatch");
            require(u32(header, 8, true) == old.length() && u32(header, 12, true) == targetSize,
                    "Base or target size mismatch");
            require(header[29] == 0 && header[30] == 0 && header[31] == 0, "Noncanonical header padding");
            int props = header[24] & 255;
            int lc = props % 9, lp = props / 9 % 5, pb = props / 45;
            long dictionary = u32(header, 25, true);
            require(pb <= 4 && lc + lp <= 4 && dictionary >= 4096 && dictionary <= MAX_DICTIONARY,
                    "LZMA memory limit or properties exceeded");
            long streamSize = unsignedSize(header, 32);
            require(streamSize >= 24 && streamSize <= targetSize + 24L * MAX_CONTROLS,
                    "Expanded stream exceeds limit");

            MessageDigest oldDigest = digest();
            CRC32 oldCrc = new CRC32();
            int read;
            while ((read = old.read(buffer)) != -1) {
                checkpoint(observer, started);
                oldDigest.update(buffer, 0, read);
                oldCrc.update(buffer, 0, read);
            }
            require(hex(oldDigest.digest()).equals(baseSha) && oldCrc.getValue() == u32(header, 16, false),
                    "Base identity mismatch");
            checkpoint(observer, started);
            // CREATE_NEW semantics: never truncate a previous output, even on failure.
            require(output.createNewFile(), "Output already exists");
            created = true;
            int controls = 0;
            long oldPos = 0, newPos = 0, consumed = 0;
            byte[] control = new byte[24], original = new byte[CHUNK];
            CRC32 newCrc = new CRC32();
            MessageDigest newDigest = digest();
            // V1 requires the encoder's EOS marker. Size alone must not accept truncation.
            try (LZMAInputStream decoded = new LZMAInputStream(compressed, -1, header[24], (int) dictionary);
                    FileOutputStream target = new FileOutputStream(output)) {
                observer.progress(0, targetSize);
                while (newPos < targetSize) {
                    checkpoint(observer, started);
                    require(++controls <= MAX_CONTROLS && streamSize - consumed >= 24, "Control budget exhausted");
                    exact(decoded, control, 0, 24);
                    consumed += 24;
                    long diff = signedOffset(control, 0), extra = signedOffset(control, 8);
                    long seek = signedOffset(control, 16);
                    require(diff >= 0 && extra >= 0 && diff <= targetSize - newPos
                            && extra <= targetSize - newPos - diff, "Invalid control lengths");
                    require(diff != 0 || extra != 0 || seek != 0, "Nonprogressing control");
                    require(diff + extra <= streamSize - consumed, "Expanded length mismatch");
                    for (int mode = 0; mode < 2; mode++) {
                        long remaining = mode == 0 ? diff : extra;
                        while (remaining > 0) {
                            checkpoint(observer, started);
                            int count = (int) Math.min(CHUNK, remaining);
                            exact(decoded, buffer, 0, count);
                            if (mode == 0) {
                                long end = add(oldPos, count);
                                long from = Math.max(0, oldPos), to = Math.min(old.length(), end);
                                if (to > from) {
                                    int offset = (int) (from - oldPos), length = (int) (to - from);
                                    old.seek(from);
                                    old.readFully(original, 0, length);
                                    for (int i = 0; i < length; i++) buffer[offset + i] += original[i];
                                }
                                oldPos = end;
                            }
                            target.write(buffer, 0, count);
                            newDigest.update(buffer, 0, count);
                            newCrc.update(buffer, 0, count);
                            consumed += count;
                            newPos += count;
                            remaining -= count;
                            observer.progress(newPos, targetSize);
                        }
                    }
                    oldPos = add(oldPos, seek);
                }
                require(consumed == streamSize && decoded.read() == -1 && compressed.read() == -1,
                        "Trailing or truncated LZMA/control data");
                require(newCrc.getValue() == u32(header, 20, false)
                        && hex(newDigest.digest()).equals(targetSha), "Target identity mismatch");
                checkpoint(observer, started);
                target.getFD().sync();
            }
            require(output.length() == targetSize, "Final output size mismatch");
            success = true;
            return new Result(targetSize, (System.nanoTime() - started) / 1_000_000, (int) dictionary, controls);
        } finally {
            if (created && !success && !output.delete() && output.exists()) {
                throw new IOException("Failed to remove partial patch output");
            }
        }
    }

    private static long add(long a, long b) throws IOException {
        try { return Math.addExact(a, b); }
        catch (ArithmeticException e) { throw new IOException("Base offset overflow", e); }
    }

    private static void checkpoint(Observer observer, long started) throws IOException {
        if (observer.cancelled() || Thread.currentThread().isInterrupted()) throw new CancellationException("Patch cancelled");
        require(System.nanoTime() - started < TIMEOUT_NANOS, "Patch deadline exceeded");
    }

    private static String hash(File file, byte[] buffer, Observer observer, long started) throws IOException {
        MessageDigest digest = digest();
        try (InputStream input = new FileInputStream(file)) {
            int count;
            while ((count = input.read(buffer)) != -1) {
                checkpoint(observer, started);
                digest.update(buffer, 0, count);
            }
        }
        return hex(digest.digest());
    }

    private static MessageDigest digest() {
        try { return MessageDigest.getInstance("SHA-256"); }
        catch (NoSuchAlgorithmException e) { throw new IllegalStateException(e); }
    }

    private static String hex(byte[] value) {
        char[] digits = "0123456789abcdef".toCharArray(), output = new char[value.length * 2];
        for (int i = 0; i < value.length; i++) {
            output[i * 2] = digits[(value[i] & 255) >>> 4];
            output[i * 2 + 1] = digits[value[i] & 15];
        }
        return new String(output);
    }

    private static long u32(byte[] data, int offset, boolean little) {
        long value = 0;
        for (int i = 0; i < 4; i++) value = (value << 8) | (data[offset + (little ? 3 - i : i)] & 255L);
        return value;
    }

    private static long unsignedSize(byte[] data, int offset) throws IOException {
        require((data[offset + 7] & 128) == 0, "Size exceeds signed range");
        return signedOffset(data, offset);
    }

    private static long signedOffset(byte[] data, int offset) {
        long value = data[offset + 7] & 127;
        for (int i = 6; i >= 0; i--) value = (value << 8) | (data[offset + i] & 255L);
        return (data[offset + 7] & 128) == 0 ? value : -value;
    }

    private static void exact(InputStream input, byte[] buffer, int offset, int count) throws IOException {
        int end = offset + count;
        while (offset < end) {
            int read = input.read(buffer, offset, end - offset);
            if (read <= 0) throw new EOFException("Truncated patch stream");
            offset += read;
        }
    }

    private static void require(boolean condition, String message) throws IOException {
        if (!condition) throw new IOException(message);
    }
}
