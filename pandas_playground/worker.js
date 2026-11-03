// Runs Python in the background so the page stays responsive.
importScripts('py/pyodide.js');
let py = null;
const say = (m) => postMessage({ type: 'status', text: m });

async function init(msg) {
  try {
    say('Starting Python');
    py = await loadPyodide({ indexURL: new URL('py/', self.location.href).href });
    say('Loading pandas and NumPy');
    await py.loadPackage(['numpy', 'pandas'], { messageCallback: () => {} });
    say('Loading the datasets');
    py.FS.mkdirTree('/home/pyodide/data');
    for (const f of msg.files) {
      const r = await fetch(new URL('data/' + f, self.location.href));
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
    postMessage({ type: 'fatal', text: String(e && e.message || e) });
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
