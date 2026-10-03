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
  res.setHeader('Permissions-Policy', 'camera=(), microphone=(), geolocation=(), payment=()');

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
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: https:",
      "connect-src 'self' https:",
      "font-src 'self' data:",
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
};
