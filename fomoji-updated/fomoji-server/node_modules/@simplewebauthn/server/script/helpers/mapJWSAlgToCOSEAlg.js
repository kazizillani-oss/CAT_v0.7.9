"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.mapJWSAlgToCOSEAlg = mapJWSAlgToCOSEAlg;
const cose_js_1 = require("./cose.js");
/**
 * Map JWS algorithms to COSE algorithm IDs
 *
 * See https://www.rfc-editor.org/rfc/rfc7518.html#section-3.1 for possible values
 */
function mapJWSAlgToCOSEAlg(alg) {
    let algCOSE;
    if (alg === 'ES256') {
        algCOSE = cose_js_1.COSEALG.ES256;
    }
    else if (alg === 'ES384') {
        algCOSE = cose_js_1.COSEALG.ES384;
    }
    else if (alg === 'ES512') {
        algCOSE = cose_js_1.COSEALG.ES512;
    }
    else if (alg === 'RS256') {
        algCOSE = cose_js_1.COSEALG.RS256;
    }
    else if (alg === 'RS384') {
        algCOSE = cose_js_1.COSEALG.RS384;
    }
    else if (alg === 'RS512') {
        algCOSE = cose_js_1.COSEALG.RS512;
    }
    else {
        throw new Error(`Unable to map JWS algorithm "${alg}" to a COSE algorithm`);
    }
    return algCOSE;
}
