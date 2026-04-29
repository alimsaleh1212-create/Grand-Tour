/**
 * SignUp page component.
 *
 * Renders a centred email + password + confirm-password form.  On submit:
 *   1. Validates client-side that passwords match (avoids a round-trip for the
 *      most common mistake).
 *   2. Calls `POST /auth/signup` via apiClient.
 *   3. On 201: automatically calls `POST /auth/login` with the same credentials
 *      so the user is signed in immediately (no "go sign in now" step).
 *   4. On 409 (email exists): displays "An account with this email already
 *      exists" inline.
 *   5. On validation error (422): surfaces the first field error from the
 *      FastAPI detail list.
 *
 * Accessibility: same pattern as SignIn — labelled inputs, role="alert" error
 * banners, spinner-on-submit.
 *
 * Navigation:
 *   - "Already have an account? Sign in" link routes to /signin.
 *
 * Implemented in Stage 7.
 */

export default function SignUp() {
  // Implemented in Stage 7
  return (
    <div>
      <h1>Sign Up</h1>
      <p>Implemented in Stage 7.</p>
    </div>
  );
}
