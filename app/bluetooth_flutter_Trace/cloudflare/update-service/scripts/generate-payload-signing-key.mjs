#!/usr/bin/env node

import { generateKeyPairSync, sign, verify } from "node:crypto";

const { privateKey, publicKey } = generateKeyPairSync("ed25519");
const privatePkcs8Der = privateKey.export({ format: "der", type: "pkcs8" });
const publicJwk = publicKey.export({ format: "jwk" });
const publicRaw = Buffer.from(base64UrlToBase64(publicJwk.x), "base64");

if (publicRaw.length !== 32) {
  throw new Error(`Unexpected Ed25519 public key length: ${publicRaw.length}`);
}

const probe = Buffer.from("trace-update-payload-key-probe", "utf8");
const signature = sign(null, probe, privateKey);
if (!verify(null, probe, publicKey, signature)) {
  throw new Error("Generated Ed25519 key pair failed self-check");
}

const keyVersion = new Date().toISOString().slice(0, 10).replaceAll("-", "");

process.stdout.write(`TRACE_UPDATE_PAYLOAD_KEY_VERSION=${keyVersion}\n`);
process.stdout.write(
  `TRACE_UPDATE_PAYLOAD_ED25519_PRIVATE_KEY_BASE64=${Buffer.from(privatePkcs8Der).toString("base64")}\n`
);
process.stdout.write(
  `TRACE_UPDATE_PAYLOAD_ED25519_PUBLIC_KEY_BASE64=${publicRaw.toString("base64")}\n`
);

function base64UrlToBase64(value) {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  return normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
}
