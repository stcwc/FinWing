/** Cognito Hosted UI configuration, injected at build time. */
export const cognitoConfig = {
  domain: import.meta.env.VITE_COGNITO_DOMAIN ?? "",
  clientId: import.meta.env.VITE_COGNITO_CLIENT_ID ?? "",
  redirectUri: `${window.location.origin}/auth/callback`,
};

export function hostedUiSignInUrl(provider?: string): string {
  const { domain, clientId, redirectUri } = cognitoConfig;
  const params = new URLSearchParams({
    client_id: clientId,
    response_type: "code",
    scope: "openid email profile",
    redirect_uri: redirectUri,
  });
  // Skip the IdP chooser and go straight to a provider (e.g. "Google").
  if (provider) params.set("identity_provider", provider);
  return `https://${domain}/oauth2/authorize?${params.toString()}`;
}

/**
 * Cognito Hosted UI logout endpoint. Clears Cognito's own session cookie (not
 * just the app cookie) so the next sign-in prompts for credentials again, then
 * redirects back to the app's sign-in page. `logout_uri` must be registered as
 * an allowed sign-out URL on the app client.
 */
export function hostedUiSignOutUrl(): string {
  const { domain, clientId } = cognitoConfig;
  const params = new URLSearchParams({
    client_id: clientId,
    logout_uri: `${window.location.origin}/signin`,
  });
  return `https://${domain}/logout?${params.toString()}`;
}
