/** Cognito Hosted UI configuration, injected at build time. */
export const cognitoConfig = {
  domain: import.meta.env.VITE_COGNITO_DOMAIN ?? "",
  clientId: import.meta.env.VITE_COGNITO_CLIENT_ID ?? "",
  redirectUri: `${window.location.origin}/auth/callback`,
};

export function hostedUiSignInUrl(): string {
  const { domain, clientId, redirectUri } = cognitoConfig;
  const params = new URLSearchParams({
    client_id: clientId,
    response_type: "code",
    scope: "openid email profile",
    redirect_uri: redirectUri,
  });
  return `https://${domain}/oauth2/authorize?${params.toString()}`;
}
