#!/usr/bin/env node
// exec into a container over the docker unix socket (no docker CLI on this host)
// usage: node doexec.js <container> <cmd> [args...]
const http = require('http');
const NAME = process.argv[2];
const CMD = process.argv.slice(3);
function post(p, body, cb) {
  const data = JSON.stringify(body);
  const r = http.request({ socketPath: '/var/run/docker.sock', path: p, method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data), 'Connection': 'Upgrade', 'Upgrade': 'tcp' } });
  r.on('upgrade', (resp, sock) => { let b = []; sock.on('data', c => b.push(c)); sock.on('end', () => cb(Buffer.concat(b))); sock.on('error', e => cb(Buffer.from(String(e)))); });
  r.on('response', resp => { let b = []; resp.on('data', c => b.push(c)); resp.on('end', () => cb(Buffer.concat(b))); });
  r.on('error', e => cb(Buffer.from(String(e))));
  r.end(data);
}
function get(p, cb) {
  const r = http.request({ socketPath: '/var/run/docker.sock', path: p, method: 'GET' });
  r.on('response', resp => { let b = []; resp.on('data', c => b.push(c)); resp.on('end', () => cb(JSON.parse(Buffer.concat(b).toString()))); });
  r.on('error', e => { console.error(e); process.exit(1); });
  r.end();
}
function demux(b) {
  if (!b.length) return '';
  if (b[0] <= 2 && b[1] === 0 && b[2] === 0 && b[3] === 0) {
    const out = []; let off = 0;
    while (off + 8 <= b.length) { const len = b.readUInt32BE(off + 4); out.push(b.slice(off + 8, off + 8 + len)); off += 8 + len; }
    return Buffer.concat(out).toString();
  }
  return b.toString();
}
get('/v1.52/containers/json?all=1', cs => {
  const c = cs.find(x => (x.Names || []).includes('/' + NAME) || x.Id.startsWith(NAME));
  if (!c) { console.error('container not found; have:', cs.map(x => x.Names)); process.exit(1); }
  post(`/v1.52/containers/${c.Id}/exec`, { Cmd: CMD, AttachStdout: true, AttachStderr: true }, b => {
    const id = JSON.parse(b.toString()).Id;
    post(`/v1.52/exec/${id}/start`, { Detach: false, Tty: false }, out => process.stdout.write(demux(out)));
  });
});
