// Runs Python in the background so the page stays responsive.
// The Python standard library and the wheels ship as base64 text (*.txt),
// because the host only serves web file types.
importScripts('py/pyodide.js');
let py = null;
const say = (m) => postMessage({ type: 'status', text: m });
const here = (p) => new URL(p, self.location.href).href;

async function bytesOf(path) {
  const r = await fetch(here(path));
  if (!r.ok) throw new Error('Could not load ' + path);
  const s = atob((await r.text()).trim());
  const out = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
  return out;
}

async function init(msg) {
  try {
    say('Downloading Python');
    const [std, ...wheels] = await Promise.all([bytesOf('py/python_stdlib.zip.txt'), ...msg.wheels.map((w) => bytesOf('py/' + w + '.txt'))]);
    say('Starting Python');
    py = await loadPyodide({ indexURL: here('py/'), stdLibURL: URL.createObjectURL(new Blob([std])) });
    say('Installing pandas and NumPy');
    py.FS.mkdirTree('/tmp/wheels');
    msg.wheels.forEach((w, i) => py.FS.writeFile('/tmp/wheels/' + w, wheels[i]));
    py.runPython(`
import zipfile, os, site, importlib
_sp = site.getsitepackages()[0]
for _w in sorted(os.listdir('/tmp/wheels')):
    zipfile.ZipFile('/tmp/wheels/' + _w).extractall(_sp)
importlib.invalidate_caches()
`);
    say('Loading the datasets');
    py.FS.mkdirTree('/home/pyodide/data');
    for (const f of msg.files) {
      const r = await fetch(here('data/' + f));
      if (!r.ok) throw new Error('Could not load data/' + f);
      py.FS.writeFile('/home/pyodide/data/' + f, await r.text());
    }
    py.FS.chdir('/home/pyodide');
    py.runPython(msg.setup);
    py.runPython(msg.checker);
    py.runPython(msg.runtime);
    const v = py.runPython('pd.__version__');
    postMessage({ type: 'ready', version: v });
  } catch (e) {
    postMessage({ type: 'fatal', text: String((e && e.message) || e) });
  }
}

onmessage = (ev) => {
  const m = ev.data;
  if (m.type === 'init') return init(m);
  if (m.type === 'run') {
    try {
      const fn = py.globals.get('_pg_run');
      const out = fn(m.code, m.solution || '', JSON.stringify(m.opts || {}), m.mode);
      fn.destroy();
      postMessage({ type: 'result', id: m.id, data: JSON.parse(out) });
    } catch (e) {
      postMessage({ type: 'result', id: m.id, data: { error: String(e), stdout: '', shown: null, check: null } });
    }
  }
};
