// Sign-in through the organisation's OpenID Connect provider. The provider and its secrets are configured
// by deployment (AUTH_OIDC_*). The access token stays in the encrypted session cookie and is read only on
// the server, where it is attached to /api/v2 requests; the browser session never exposes it.

import type { NextAuthOptions } from "next-auth";

const issuer = process.env.AUTH_OIDC_ISSUER?.replace(/\/$/, "");

export const providerConfigured = Boolean(issuer && process.env.AUTH_OIDC_CLIENT_ID);

export const authOptions: NextAuthOptions = {
  providers: providerConfigured
    ? [
        {
          id: "oidc",
          name: process.env.AUTH_OIDC_NAME ?? "your organisation",
          type: "oauth",
          wellKnown: `${issuer}/.well-known/openid-configuration`,
          clientId: process.env.AUTH_OIDC_CLIENT_ID,
          clientSecret: process.env.AUTH_OIDC_CLIENT_SECRET,
          client: process.env.AUTH_OIDC_CLIENT_SECRET ? undefined : { token_endpoint_auth_method: "none" },
          authorization: {
            params: {
              scope: "openid profile email",
              ...(process.env.AUTH_OIDC_AUDIENCE ? { audience: process.env.AUTH_OIDC_AUDIENCE } : {}),
            },
          },
          checks: ["pkce", "state"],
          idToken: true,
          profile: (profile) => ({ id: profile.sub, name: profile.name ?? profile.preferred_username ?? null, email: profile.email ?? null }),
        },
      ]
    : [],
  session: { strategy: "jwt" },
  pages: { signIn: "/sign-in" },
  callbacks: {
    jwt({ token, account }) {
      if (account) {
        token.accessToken = account.access_token;
        token.expiresAt = account.expires_at;
      }
      return token;
    },
    session({ session, token }) {
      return { ...session, expiresAt: token.expiresAt };
    },
  },
};
