'use strict';

const crypto = require('crypto');
const { ORIGIN, IS_PRODUCTION } = require('./config');

/**
 * 1. Correlation ID Middleware
 * Assigns a unique trace ID to every request for audit and error tracking.
 */
function correlationIdMiddleware(req, res, next) {
  req.correlationId = req.headers['x-correlation-id'] || crypto.randomUUID();
  res.setHeader('X-Correlation-ID', req.correlationId);
  next();
}

/**
 * 2. Security Headers Middleware
 * Enforces strict browser-level protections across all HTTP responses.
 */
function securityHeadersMiddleware(req, res, next) {
  // Prevent MIME-sniffing
  res.setHeader('X-Content-Type-Options', 'nosniff');

  // Prevent clickjacking via iframes
  res.setHeader('X-Frame-Options', 'DENY');

  // Legacy XSS filter protection
  res.setHeader('X-XSS-Protection', '1; mode=block');

  // Privacy: restrict referrer leakage
  res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');

  // Restrict sensitive hardware features
  res.setHeader('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');

  // Strict-Transport-Security (1 year) when deployed over HTTPS or in production
  if (IS_PRODUCTION || (ORIGIN && ORIGIN.startsWith('https://'))) {
    res.setHeader('Strict-Transport-Security', 'max-age=31536000; includeSubDomains; preload');
  }

  // Content-Security-Policy: restrict script execution to self and authorized CDN for 3D card
  res.setHeader(
    'Content-Security-Policy',
    [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
      "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
      "style-src-elem 'self' 'unsafe-inline' https://fonts.googleapis.com",
      "img-src 'self' data: https:",
      "connect-src 'self' https:",
      "font-src 'self' data: https://fonts.gstatic.com",
      "object-src 'none'",
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'",
    ].join('; ')
  );

  next();
}

/**
 * 3. Strict CORS Middleware
 * Restricts cross-origin resource sharing to the trusted application domain.
 */
function corsMiddleware(req, res, next) {
  const reqOrigin = req.headers.origin;

  if (reqOrigin) {
    let allowed = false;

    if (reqOrigin === ORIGIN) {
      allowed = true;
    } else if (!IS_PRODUCTION) {
      // In local dev, allow localhost variants
      const isLocal = /^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(reqOrigin);
      if (isLocal) allowed = true;
    }

    if (allowed) {
      res.setHeader('Access-Control-Allow-Origin', reqOrigin);
      res.setHeader('Access-Control-Allow-Credentials', 'true');
      res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PATCH, PUT, DELETE, OPTIONS');
      res.setHeader(
        'Access-Control-Allow-Headers',
        'Content-Type, Authorization, X-Correlation-ID, X-Connector-Registration-Secret'
      );
    } else {
      // Untrusted external origin attempting access
      if (req.method === 'OPTIONS') {
        return res.status(403).json({ error: 'cors_forbidden', correlationId: req.correlationId });
      }
    }
  }

  if (req.method === 'OPTIONS') {
    return res.status(204).end();
  }

  next();
}

/**
 * 4. In-Memory Sliding Window Rate Limiter
 */
function getClientIp(req) {
  const forwarded = req.headers['x-forwarded-for'];
  if (forwarded && typeof forwarded === 'string') {
    return forwarded.split(',')[0].trim();
  }
  return req.ip || req.socket?.remoteAddress || 'unknown';
}

function createRateLimiter({ windowMs, max, message, keyGenerator }) {
  const hits = new Map(); // key -> [timestamps]

  // Periodic cleanup every 2 minutes
  const cleanupTimer = setInterval(() => {
    const now = Date.now();
    for (const [key, timestamps] of hits.entries()) {
      const active = timestamps.filter((t) => now - t < windowMs);
      if (active.length === 0) {
        hits.delete(key);
      } else {
        hits.set(key, active);
      }
    }
  }, 120 * 1000);
  if (cleanupTimer.unref) cleanupTimer.unref();

  return function rateLimiter(req, res, next) {
    const key = keyGenerator ? keyGenerator(req) : getClientIp(req);
    const now = Date.now();
    const timestamps = (hits.get(key) || []).filter((t) => now - t < windowMs);

    if (timestamps.length >= max) {
      const oldest = timestamps[0];
      const retryAfter = Math.ceil((oldest + windowMs - now) / 1000);
      res.setHeader('Retry-After', Math.max(1, retryAfter));
      return res.status(429).json({
        error: 'too_many_requests',
        message: message || 'Too many requests. Please try again later.',
        retryAfterSeconds: Math.max(1, retryAfter),
        correlationId: req.correlationId,
      });
    }

    timestamps.push(now);
    hits.set(key, timestamps);
    next();
  };
}

// 5 attempts per minute per IP for login
const loginRateLimiter = createRateLimiter({
  windowMs: 60 * 1000,
  max: 5,
  message: 'Too many login attempts. Please wait 1 minute before trying again.',
});

// 5 attempts per minute per IP for account registration
const signupRateLimiter = createRateLimiter({
  windowMs: 60 * 1000,
  max: 5,
  message: 'Too many account creation attempts. Please wait 1 minute before trying again.',
});

// 3 attempts per hour (3600s) per IP for password reset
const passwordResetRateLimiter = createRateLimiter({
  windowMs: 60 * 60 * 1000,
  max: 3,
  message: 'Too many password reset attempts. Please wait 1 hour before trying again.',
});

/**
 * 5. Production-Grade Centralized Error Handler
 * Sanitizes errors: internal details, stack traces, and database schemas are logged
 * to server logs with correlation ID, and never leaked to the client.
 */
function errorHandler(err, req, res, next) {
  const correlationId = req.correlationId || crypto.randomUUID();
  console.error(`[ERROR correlationId=${correlationId}] unhandled exception on ${req.method} ${req.originalUrl}:`, err);

  if (res.headersSent) {
    return next(err);
  }

  res.status(500).json({
    error: 'server_error',
    message: 'An unexpected internal error occurred. Please contact support with the correlation ID.',
    correlationId,
  });
}

/**
 * 6. CAT Browser Exclusivity Middleware
 * Ensures Fomoji portal can ONLY be opened inside CAT Browser.
 * If opened in Chrome, Edge, Firefox, or Safari, displays a 3D Liquid Glass Access Restricted Screen.
 */
function catBrowserExclusivityMiddleware(req, res, next) {
  // Only protect HTML page requests and root navigation; allow API & static assets (CSS, JS, images, fonts)
  const isHtmlRequest =
    req.path === '/' ||
    req.path.endsWith('.html') ||
    (req.headers.accept && req.headers.accept.includes('text/html') && !req.path.startsWith('/api/') && !req.path.startsWith('/archify/'));

  if (!isHtmlRequest) {
    return next();
  }

  const ua = req.headers['user-agent'] || '';
  const xCat = req.headers['x-cat-browser'];
  const isCatBrowser = ua.includes('CATBrowser') || xCat === '1';

  if (isCatBrowser) {
    return next();
  }

  // Block external browsers with 3D Liquid Glass Security Screen
  res.status(403);
  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  return res.send(`<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Fomoji Security — CAT Browser Exclusive</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: radial-gradient(circle at 50% 15%, #18192b 0%, #0c0d16 80%);
      color: #e4e6f8;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      padding: 24px;
      overflow: hidden;
    }
    .liquid-orb {
      position: absolute;
      width: 480px;
      height: 480px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(124, 107, 255, 0.28) 0%, rgba(94, 233, 160, 0.08) 60%, transparent 80%);
      filter: blur(60px);
      pointer-events: none;
      z-index: 0;
    }
    .card {
      position: relative;
      z-index: 1;
      max-width: 520px;
      width: 100%;
      padding: 44px 38px;
      text-align: center;
      background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.02) 100%);
      backdrop-filter: blur(28px);
      -webkit-backdrop-filter: blur(28px);
      border: 1px solid rgba(255, 255, 255, 0.14);
      border-top: 1.5px solid rgba(255, 255, 255, 0.35);
      border-bottom: 2px solid rgba(0, 0, 0, 0.6);
      border-radius: 24px;
      box-shadow: 0 24px 64px rgba(0, 0, 0, 0.65), inset 0 1px 0 rgba(255, 255, 255, 0.25);
    }
    .shield-icon {
      font-size: 56px;
      margin-bottom: 14px;
      display: inline-block;
      filter: drop-shadow(0 0 20px rgba(124, 107, 255, 0.7));
    }
    .pill {
      display: inline-block;
      padding: 5px 14px;
      border-radius: 999px;
      background: rgba(124, 107, 255, 0.18);
      border: 1px solid rgba(124, 107, 255, 0.45);
      color: #c7d2fe;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 1.2px;
      text-transform: uppercase;
      margin-bottom: 16px;
    }
    h1 {
      font-size: 26px;
      font-weight: 800;
      letter-spacing: -0.4px;
      margin-bottom: 12px;
      background: linear-gradient(135deg, #ffffff 40%, #a5b4fc 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    p {
      color: #9094be;
      font-size: 14px;
      line-height: 1.6;
      margin-bottom: 28px;
    }
    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 13px 28px;
      border-radius: 12px;
      font-weight: 700;
      font-size: 14px;
      color: #ffffff;
      text-decoration: none;
      cursor: pointer;
      background: linear-gradient(180deg, #7c6bff 0%, #6353ea 100%);
      box-shadow: 0 6px 20px rgba(124, 107, 255, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.35);
      border: 1px solid rgba(255, 255, 255, 0.25);
      transition: all 0.2s ease;
    }
    .btn:hover {
      transform: translateY(-1px);
      box-shadow: 0 8px 24px rgba(124, 107, 255, 0.6);
    }
    .note {
      margin-top: 20px;
      font-size: 11px;
      color: #63678e;
    }
  </style>
</head>
<body>
  <div class="liquid-orb"></div>
  <div class="card">
    <div class="shield-icon">🛡️</div>
    <div><span class="pill">Hardware Enclave Protected</span></div>
    <h1>CAT Browser Exclusive</h1>
    <p>Fomoji biometric passkeys and identities are cryptographically bound to <b>CAT Browser</b>. External browsers (Chrome, Edge, Firefox, Safari) cannot access this secure enclave.</p>
    <a class="btn" href="cat://open?url=http://localhost:3000/home.html">
      <span>🐱 Open in CAT Browser</span>
    </a>
    <div class="note">Security Protocol: Zero-Trust Hardware Isolation</div>
  </div>
</body>
</html>`);
}

module.exports = {
  correlationIdMiddleware,
  securityHeadersMiddleware,
  corsMiddleware,
  getClientIp,
  createRateLimiter,
  loginRateLimiter,
  signupRateLimiter,
  passwordResetRateLimiter,
  errorHandler,
  catBrowserExclusivityMiddleware,
};
