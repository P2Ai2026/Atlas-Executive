/**
 * Auth stub for AppleScript mode.
 * No OAuth needed — Mail.app is already authenticated.
 * These functions exist so main.js doesn't need changes.
 */

function isAuthenticated() {
  return true; // Mail.app handles auth natively
}

async function getToken() {
  return null; // not used in AppleScript mode
}

async function startAuth() {
  // Open Mail.app so the user can confirm it's running
  const { exec } = require('child_process');
  exec('open -a Mail');
  return { ok: true, message: 'Mail.app opened. Make sure your account is set up there.' };
}

module.exports = { isAuthenticated, getToken, startAuth };
