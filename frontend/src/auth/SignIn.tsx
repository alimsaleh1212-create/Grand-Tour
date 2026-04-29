/**
 * SignIn page component.
 *
 * Renders a centred email + password form.  On submit:
 *   1. Calls `POST /auth/login` via apiClient.
 *   2. On success: passes the returned `access_token` to `useAuth().login()`,
 *      which stores it and navigates to /chat.
 *   3. On 401: displays "Invalid credentials" inline.
 *   4. On network/server error: displays a generic error banner.
 *
 * Accessibility:
 *   - `<label>` elements associated with inputs via `htmlFor`.
 *   - Error messages in an `role="alert"` element so screen readers announce
 *     them without re-focusing.
 *   - Submit button disabled and shows a spinner during the in-flight request.
 *
 * Navigation:
 *   - "Don't have an account? Sign up" link routes to /signup.
 *
 * Implemented in Stage 7.
 */

export default function SignIn() {
  // Implemented in Stage 7
  return (
    <div>
      <h1>Sign In</h1>
      <p>Implemented in Stage 7.</p>
    </div>
  );
}
