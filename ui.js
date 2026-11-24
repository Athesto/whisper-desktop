const choose = document.querySelector('#choose');
const start = document.querySelector('#start');
const save = document.querySelector('#save');
const model = document.querySelector('#model');
const language = document.querySelector('#language');
const statusText = document.querySelector('#status');
const progress = document.querySelector('#progress');
const appVersion = document.querySelector('#app-version');
let api;
let filename;
let phase = 'idle';
let busy = false;

function updateButtons() {
  const locked = busy || phase === 'running';
  choose.disabled = locked;
  start.disabled = locked || !filename;
  save.disabled = locked || phase !== 'done';
  model.disabled = locked;
  language.disabled = locked;
}

function showMessage(message, error = false) {
  if (statusText.textContent !== message) statusText.textContent = message;
  statusText.dataset.error = error;
}

function render(state) {
  phase = state.phase;
  if (state.version && appVersion.hidden) {
    appVersion.textContent = "v" + state.version;
    appVersion.hidden = false;
  }
  showMessage(state.message, phase === 'error');
  progress.hidden = phase !== 'running';
  if (state.progress === null) progress.removeAttribute('value');
  else progress.value = state.progress;
  updateButtons();
}

async function run(action) {
  busy = true;
  updateButtons();
  try {
    await action();
  } catch (error) {
    showMessage(error.message || String(error), true);
  } finally {
    busy = false;
    updateButtons();
  }
}

async function poll() {
  try {
    render(await api.status());
  } catch {
    showMessage('Se perdió la comunicación con la aplicación. Reintentando…', true);
  }
  if (phase === 'running') setTimeout(poll, 500);
}

window.addEventListener('pywebviewready', () => {
  api = window.pywebview.api;
  run(async () => render(await api.status()));
  choose.addEventListener('click', () => run(async () => {
    const selected = await api.choose_video();
    if (selected) {
      filename = selected;
      document.querySelector('#filename').textContent = filename;
      render(await api.status());
    }
  }));
  start.addEventListener('click', () => run(async () => {
    if (await api.start(model.value, language.value)) {
      render({phase: 'running', message: 'Cargando modelo de Whisper…', progress: null});
      await poll();
    }
  }));
  save.addEventListener('click', () => run(async () => {
    const result = await api.save();
    if (result?.error) showMessage(result.error, true);
    else if (result) showMessage(`Guardado como ${result.name}.`);
  }));
}, {once: true});
