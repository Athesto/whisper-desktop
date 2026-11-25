const choose = document.querySelector('#choose');
const start = document.querySelector('#start');
const save = document.querySelector('#save');
const model = document.querySelector('#model');
const language = document.querySelector('#language');
const statusText = document.querySelector('#status');
const progress = document.querySelector('#progress');
const appVersion = document.querySelector('#app-version');
let api;
const dropZone = document.querySelector('#drop-zone');
const fileCount = document.querySelector('#filename');
const queue = document.querySelector('#queue');
const format = document.querySelector('#format');
const formatField = document.querySelector('#format-field');
const metalField = document.querySelector('#metal-field');
const metal = document.querySelector('#metal');
const device = document.querySelector('#device');
let files = [];
let renderedResults = -1;
let phase = 'idle';
let busy = false;

function updateButtons() {
  const locked = busy || phase === 'running';
  choose.disabled = locked;
  const batch = files.length > 1;
  start.disabled = locked || !files.length;
  start.textContent = batch ? 'Transcribir lote…' : 'Transcribir';
  save.hidden = batch;
  formatField.hidden = !batch;
  formatField.parentElement.classList.toggle('has-batch', batch);
  format.disabled = locked;
  metal.disabled = locked || metalField.hidden;
  save.disabled = locked || phase !== 'done';
  model.disabled = locked;
  language.disabled = locked;
}

function showMessage(message, error = false) {
  if (statusText.textContent !== message) statusText.textContent = message;
  statusText.dataset.error = error;
}

function renderQueue(results) {
  if (renderedResults === results.length) return;
  renderedResults = results.length;
  queue.hidden = files.length < 2;
  queue.replaceChildren(...files.map((name, index) => {
    const item = document.createElement('li');
    const result = results[index];
    item.textContent = result ? name + ' · ' + result.message : name;
    if (result?.error) item.dataset.error = 'true';
    return item;
  }));
}

function setSelection(selected) {
  files = selected;
  renderedResults = -1;
  fileCount.textContent = files.length > 1 ? files.length + ' archivos seleccionados' : files[0];
  fileCount.title = files.length === 1 ? files[0] : '';
}

function refreshSelection() {
  return run(async () => {
    const state = await api.status();
    if (state.files.length) setSelection(state.files);
    render(state);
  });
}

document.addEventListener('dragover', (event) => {
  event.preventDefault();
  const acceptsFiles = !choose.disabled && dropZone.contains(event.target) &&
    Array.from(event.dataTransfer.types).includes('Files');
  event.dataTransfer.dropEffect = acceptsFiles ? 'copy' : 'none';
  dropZone.classList.toggle('is-dragging', acceptsFiles);
});
dropZone.addEventListener('dragleave', (event) => {
  if (!dropZone.contains(event.relatedTarget)) dropZone.classList.remove('is-dragging');
});
document.addEventListener('drop', (event) => {
  event.preventDefault();
  dropZone.classList.remove('is-dragging');
});

function render(state) {
  renderQueue(state.results ?? []);
  phase = state.phase;
  if (state.metal_available !== undefined) metalField.hidden = !state.metal_available;
  device.hidden = !state.device;
  device.textContent = state.device === 'mps' ? 'Dispositivo: GPU (Metal)' : 'Dispositivo: CPU';
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
  refreshSelection();
  window.addEventListener('whisper-files-selected', refreshSelection);
  window.addEventListener('whisper-files-unavailable', () => {
    if (!choose.disabled) showMessage('No se pudo leer el archivo arrastrado. Usa Elegir archivos.', true);
  });
  choose.addEventListener('click', () => run(async () => {
    const selected = await api.choose_files();
    if (selected) {
      setSelection(selected);
      render(await api.status());
    }
  }));
  start.addEventListener('click', () => run(async () => {
    const useMetal = !metalField.hidden && metal.checked;
    if (await api.start(model.value, language.value, format.value, useMetal)) {
      render({phase: 'running', message: 'Cargando modelo de Whisper…', progress: null, device: useMetal ? 'mps' : 'cpu'});
      await poll();
    }
  }));
  save.addEventListener('click', () => run(async () => {
    const result = await api.save();
    if (result?.error) showMessage(result.error, true);
    else if (result) showMessage(`Guardado como ${result.name}.`);
  }));
}, {once: true});
