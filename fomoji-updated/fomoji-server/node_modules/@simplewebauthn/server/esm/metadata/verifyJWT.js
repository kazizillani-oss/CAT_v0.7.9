import { convertX509PublicKeyToCOSE } from '../helpers/convertX509PublicKeyToCOSE.js';
import { isoBase64URL, isoUint8Array } from '../helpers/iso/index.js';
import { COSEKEYS, isCOSEPublicKeyEC2, isCOSEPublicKeyRSA } from '../helpers/cose.js';
import { mapJWSAlgToCOSEAlg } from '../helpers/mapJWSAlgToCOSEAlg.js';
import { verifyEC2 } from '../helpers/iso/isoCrypto/verifyEC2.js';
import { verifyRSA } from '../helpers/iso/isoCrypto/verifyRSA.js';
/**
 * Lightweight verification for FIDO MDS JWTs. Supports use of EC2 and RSA.
 *
 * If this ever needs to support more JWS algorithms, here's the list of them:
 *
 * https://www.rfc-editor.org/rfc/rfc7518.html#section-3.1
 *
 * (Pulled from https://www.rfc-editor.org/rfc/rfc7515#section-4.1.1)
 */
export function verifyJWT(jwt, leafCert) {
    const [header, payload, signature] = jwt.split('.');
    const certCOSE = convertX509PublicKeyToCOSE(leafCert);
    const data = isoUint8Array.fromUTF8String(`${header}.${payload}`);
    const signatureBytes = isoBase64URL.toBuffer(signature);
    // We just need the `alg` from the header, so only partially define the shape of it
    const headerJSON = JSON.parse(isoBase64URL.toUTF8String(header));
    const jwtHeaderHashAlgCOSE = mapJWSAlgToCOSEAlg(headerJSON.alg);
    if (isCOSEPublicKeyEC2(certCOSE)) {
        return verifyEC2({
            data,
            signature: signatureBytes,
            cosePublicKey: certCOSE,
            shaHashOverride: jwtHeaderHashAlgCOSE,
        });
    }
    else if (isCOSEPublicKeyRSA(certCOSE)) {
        return verifyRSA({
            data,
            signature: signatureBytes,
            cosePublicKey: certCOSE,
            shaHashOverride: jwtHeaderHashAlgCOSE,
        });
    }
    const kty = certCOSE.get(COSEKEYS.kty);
    throw new Error(`JWT verification with public key of kty ${kty} is not supported by this method`);
}
