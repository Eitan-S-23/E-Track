package com.wen.gaia.gaia;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.CancellationException;

/** Executed on both CI JDKs against vectors produced independently by Python/liblzma. */
public final class BsdiffLzmaPatchTest {
    private BsdiffLzmaPatchTest() {}

    public static void main(String[] args) throws Exception {
        File directory = new File(args[0]);
        List<String> cases = Files.readAllLines(new File(directory, "cases.tsv").toPath(), StandardCharsets.UTF_8);
        int count = 0;
        for (String line : cases) {
            String[] c = line.split("\t");
            String name = c[0], expected = c[1];
            File base = new File(directory, name + ".old"), patch = new File(directory, name + ".patch");
            File output = new File(directory, name + ".output");
            byte[] oldBytes = Files.readAllBytes(base.toPath()), patchBytes = Files.readAllBytes(patch.toPath());
            byte[] target = Files.readAllBytes(new File(directory, name + ".new").toPath());
            if (expected.equals("existing")) Files.write(output.toPath(), new byte[]{99});
            final long[] progress = {0};
            BsdiffLzmaPatch.Observer observer = new BsdiffLzmaPatch.Observer() {
                public boolean cancelled() {
                    return expected.equals("cancel-before") || (expected.equals("cancel-during") && progress[0] >= 65536);
                }
                public void progress(long completed, long total) {
                    if (completed < progress[0] || completed > total || total != target.length) throw new AssertionError("Progress drift");
                    progress[0] = completed;
                }
            };
            boolean failed = false;
            try {
                String zeros = new String(new char[64]).replace('\0', '0');
                BsdiffLzmaPatch.Result result = BsdiffLzmaPatch.apply(base, patch, output, c[2],
                    expected.equals("patch-sha") ? zeros : c[3], expected.equals("target-sha") ? zeros : c[4],
                    Long.parseLong(c[5]) + (expected.equals("expected-size") ? 1 : 0), observer);
                if (!expected.equals("ok")) throw new AssertionError("Malformed patch accepted: " + name);
                if (!Arrays.equals(Files.readAllBytes(output.toPath()), target) || result.bytes != target.length
                        || result.dictionaryBytes != 4096 || result.controls < 1) throw new AssertionError("Reconstruction drift: " + name);
            } catch (java.io.IOException | CancellationException error) {
                failed = true;
                if (expected.equals("ok")) throw new AssertionError("Valid vector rejected: " + name, error);
                if (expected.startsWith("cancel-") && !(error instanceof CancellationException)) throw error;
            }
            if (failed && expected.equals("existing")) {
                if (!Arrays.equals(Files.readAllBytes(output.toPath()), new byte[]{99})) throw new AssertionError("Existing output changed");
            } else if (failed && output.exists()) throw new AssertionError("Partial output leaked: " + name);
            if (!Arrays.equals(oldBytes, Files.readAllBytes(base.toPath())) || !Arrays.equals(patchBytes, Files.readAllBytes(patch.toPath()))) {
                throw new AssertionError("Input changed");
            }
            count++;
            System.out.println("APP_PATCH_CASE " + name + " PASS");
        }
        System.out.println("APP_PATCH_TESTS_PASS " + count);
    }
}
