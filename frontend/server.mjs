import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
const assets = new Map([['/', ['index.html', 'text/html']], ['/style.css', ['style.css', 'text/css']], ...['app','api','icons','ui','views','security','landing','motion'].map(name=>['/'+name+'.js',[name+'.js','text/javascript']]), ['/assets/InterVariable.woff2',['assets/InterVariable.woff2','font/woff2']]]);
const HOST = process.env.HOST || '127.0.0.1';
const PORT = Number(process.env.PORT) || 3000;
// Same-origin proxy deployments use 'self'; local dev talks to the API directly.
const API_ORIGIN = process.env.API_ORIGIN || 'http://127.0.0.1:8000';
const server = createServer(async (request, response) => {
  const asset = assets.get(request.url?.split('?')[0]);
  const headers = {
    'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
    'X-Frame-Options': 'DENY', 'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
    'Content-Security-Policy': `default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data:; connect-src ${API_ORIGIN}; frame-ancestors 'none'; base-uri 'none'; form-action 'none'`,
  };
  if (!asset || !['GET', 'HEAD'].includes(request.method)) { response.writeHead(404, headers).end('Not found'); return; }
  try { const body = await readFile(new URL(asset[0], import.meta.url)); response.writeHead(200, { ...headers, 'Content-Type': asset[1] + '; charset=utf-8' }); response.end(request.method === 'HEAD' ? undefined : body); }
  catch { response.writeHead(500, headers).end('Unable to load the page'); }
});
server.listen(PORT, HOST, () => console.log(`SecureVault frontend: http://${HOST}:${PORT}`));
