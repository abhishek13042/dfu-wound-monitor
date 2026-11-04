// A local OpenID Connect provider for the workflow test (REQ-P08-S02-006). It signs any visitor in at once,
// so it is for a disposable local stack only. Point both sides at it:
//   web: AUTH_OIDC_ISSUER=http://localhost:8085 AUTH_OIDC_CLIENT_ID=dfu-web AUTH_OIDC_AUDIENCE=dfu-api
//   api: DFU_AUTH_ISSUER=http://localhost:8085 DFU_AUTH_AUDIENCE=dfu-api DFU_AUTH_JWKS_URL=http://localhost:8085/jwks
import { OAuth2Server } from "oauth2-mock-server";

const PORT = Number(process.env.OIDC_PORT ?? 8085);
const AUDIENCE = process.env.OIDC_AUDIENCE ?? "dfu-api";

const server = new OAuth2Server();
await server.issuer.keys.generate("RS256");
server.service.on("beforeTokenSigning", (token, request) => {
  const client = request.body?.client_id ?? "dfu-web";
  token.payload.sub = "e2e-user";
  token.payload.email = "e2e@example.test";
  // The ID token is for the web app and the access token for the API; one audience list serves both.
  token.payload.aud = [client, AUDIENCE];
  token.payload.azp = client;
});
await server.start(PORT, "localhost");
console.log(`OIDC provider at ${server.issuer.url}`);
