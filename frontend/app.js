const screen = document.querySelector('#screen');
const topics = {
  'Technology and AI': ['Explain how a piece of technology helps you learn.', 'Discuss one way AI could change everyday life.'],
  'Education': ['Describe one change that could improve learning.', 'Explain a skill schools should teach.'],
  'Society and culture': ['Describe a tradition that brings people together.', 'Explain how art can bring a community together.'],
  'Environment': ['Suggest a way your community could reduce waste.', 'Explain why a local green space matters.'],
  'Business': ['Describe a business idea that solves an everyday problem.', 'Explain what makes a customer experience memorable.'],
  'Personal experiences': ['Describe a challenge that taught you something.', 'Explain a hobby you would recommend to someone.'],
  'Current events': ['Explain a recent event that matters to your community.', 'Discuss a current issue and a possible response.']
};
const questions = [
  'Tell me about a time you solved a problem.',
  'Describe a time you worked with a team.',
  'Tell me about a challenge and what you learned from it.'
];

let interval;
let slidesUrl;
let recordingStream;
let recorder;
let recordingUrl;
let recordingSession = 0;

function releaseMicrophone() {
  recordingStream?.getTracks().forEach(track => track.stop());
  recordingStream = undefined;
}

function discardRecording() {
  recordingSession++;
  if (recorder && recorder.state !== 'inactive') recorder.stop();
  recorder = undefined;
  releaseMicrophone();
  if (recordingUrl) URL.revokeObjectURL(recordingUrl);
  recordingUrl = undefined;
}

const skills = [
  ['Pacing', 'Read a short paragraph slowly, then repeat at a comfortable pace.'],
  ['Clarity', 'Explain a familiar idea in plain language in one minute.'],
  ['Structure', 'Organize an answer into a beginning, example, and takeaway.']
];
const storageKey = 'speakly-dashboard';
let dashboard = { name: '', goal: '', practiceDays: [], focus: [], improved: [] };

try {
  dashboard = { ...dashboard, ...JSON.parse(localStorage.getItem(storageKey)) };
} catch {
  // The dashboard remains usable in memory when browser storage is unavailable.
}

function saveDashboard() {
  try {
    localStorage.setItem(storageKey, JSON.stringify(dashboard));
  } catch {
    // Keep the current session usable in storage-restricted browsers.
  }
}

function localDateKey(date = new Date()) {
  return [date.getFullYear(), date.getMonth() + 1, date.getDate()]
    .map(value => String(value).padStart(2, '0')).join('-');
}

function updateHome() {
  const name = dashboard.name;
  screen.querySelector('#greeting').textContent = 'Hello, ' + (name || 'speaker') + '!';
  screen.querySelector('#edit-profile').textContent = name ? [...name][0].toUpperCase() : 'S';
  screen.querySelector('#practice-days').textContent = dashboard.practiceDays.length;
  screen.querySelector('#improved-skills').textContent = dashboard.improved.length
    ? dashboard.improved.join(', ') + ' · Self-reported'
    : 'Track improvements in your roadmap.';
  if (!dashboard.goal) return;

  const today = Date.parse(localDateKey());
  const days = Math.round((Date.parse(dashboard.goal) - today) / 86400000);
  screen.querySelector('#goal-value').textContent = days > 0 ? days + (days === 1 ? ' day' : ' days')
    : days === 0 ? 'Goal day' : 'Date passed';
  screen.querySelector('#goal-caption').textContent = days > 0 ? 'until your goal · Edit date' : 'Tap to edit your date';
}

function bindDashboardDialog(dialogId, buttonId, fieldName, key) {
  const dialog = screen.querySelector(dialogId);
  const input = dialog.querySelector('input');
  screen.querySelector(buttonId).addEventListener('click', () => {
    input.value = dashboard[key];
    dialog.returnValue = '';
    dialog.showModal();
  });
  dialog.addEventListener('close', () => {
    if (dialog.returnValue !== 'save') return;
    dashboard[key] = dialog.querySelector('form').elements.namedItem(fieldName).value.trim();
    saveDashboard();
    updateHome();
  });
}

function bindHome() {
  updateHome();
  bindDashboardDialog('#goal-dialog', '#edit-goal', 'target', 'goal');
  bindDashboardDialog('#profile-dialog', '#edit-profile', 'displayName', 'name');
}

function bindRoadmap() {
  const list = screen.querySelector('#skill-list');
  for (const [skill, exercise] of skills) {
    const row = document.createElement('section');
    row.className = 'skill-row';
    const heading = document.createElement('h2');
    heading.textContent = skill;
    const description = document.createElement('p');
    description.textContent = exercise;
    row.append(heading, description);

    for (const [key, text] of [['focus', 'Add to my focus'], ['improved', 'I noticed improvement']]) {
      const label = document.createElement('label');
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.checked = dashboard[key].includes(skill);
      checkbox.addEventListener('change', () => {
        dashboard[key] = checkbox.checked
          ? [...dashboard[key], skill]
          : dashboard[key].filter(value => value !== skill);
        saveDashboard();
      });
      label.append(checkbox, text);
      row.append(label);
    }
    list.append(row);
  }
}

function show(template) {
  clearInterval(interval);
  if (template !== 'practice' && template !== 'summary') discardRecording();
  if (slidesUrl) {
    URL.revokeObjectURL(slidesUrl);
    slidesUrl = undefined;
  }
  screen.replaceChildren(document.getElementById(template).content.cloneNode(true));
  screen.classList.toggle('dashboard', template === 'home');
  window.scrollTo(0, 0);
  screen.focus({ preventScroll: true });
}

function pick(items) {
  return items[Math.floor(Math.random() * items.length)];
}

function formatTime(seconds) {
  return [
    Math.floor(seconds / 60),
    String(seconds % 60).padStart(2, '0')
  ].join(':');
}

function startPractice(mode, settings) {
  show('practice');
  screen.querySelector('#practice-mode').textContent =
    mode === 'presentation' ? 'Presentation rehearsal' : 'Mock interview';
  screen.querySelector('#prompt').textContent = settings.prompt;
  if (settings.audience) {
    screen.querySelector('#audience').textContent = 'Audience: ' + settings.audience;
  }
  if (mode === 'presentation') {
    screen.querySelector('#practice-details').textContent = settings.style + ' · ' + settings.difficulty;
  }
  if (settings.slides?.size) {
    slidesUrl = URL.createObjectURL(settings.slides);
    const link = screen.querySelector('#slides');
    link.href = slidesUrl;
    link.hidden = false;
  }

  let recordingFinished = Promise.resolve();
  if (mode === 'presentation') {
    const controls = screen.querySelector('#recording-controls');
    const status = screen.querySelector('#recording-status');
    const button = screen.querySelector('#record-audio');
    controls.hidden = false;
    button.addEventListener('click', async () => {
      if (recorder && recorder.state !== 'inactive') {
        recorder.stop();
        button.disabled = true;
        return;
      }
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
        status.textContent = 'Audio recording is unavailable in this browser.';
        return;
      }
      const session = ++recordingSession;
      button.disabled = true;
      status.textContent = 'Waiting for microphone permission…';
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        if (session !== recordingSession || !controls.isConnected) {
          stream.getTracks().forEach(track => track.stop());
          return;
        }
        recordingStream = stream;
        recorder = new MediaRecorder(stream);
        const activeRecorder = recorder;
        const chunks = [];
        recordingFinished = new Promise(resolve => {
          recorder.addEventListener('dataavailable', event => {
            if (event.data.size) chunks.push(event.data);
          });
          recorder.addEventListener('stop', () => {
            stream.getTracks().forEach(track => track.stop());
            if (recordingStream === stream) recordingStream = undefined;
            if (session === recordingSession && chunks.length) {
              if (recordingUrl) URL.revokeObjectURL(recordingUrl);
              recordingUrl = URL.createObjectURL(new Blob(chunks, { type: activeRecorder.mimeType }));
            }
            if (controls.isConnected) {
              status.textContent = 'Recording stopped. You can listen after finishing practice.';
              button.textContent = 'Record again';
              button.disabled = false;
            }
            resolve();
          }, { once: true });
        });
        recorder.start();
        status.textContent = 'Microphone on — recording now.';
        button.textContent = 'Stop recording';
        button.disabled = false;
      } catch {
        releaseMicrophone();
        if (session === recordingSession && controls.isConnected) {
          status.textContent = 'Microphone access failed. Check your browser permissions and try again.';
          button.disabled = false;
        }
      }
    });
  }

  const label = screen.querySelector('#timer-label');
  const timer = screen.querySelector('#timer');
  const advance = screen.querySelector('#advance');
  let preparing = settings.prep > 0;
  let startedAt = performance.now();

  function updateTimer() {
    const elapsed = Math.floor((performance.now() - startedAt) / 1000);
    if (preparing && elapsed >= settings.prep) {
      preparing = false;
      startedAt += settings.prep * 1000;
      updateTimer();
      return;
    }
    const limit = preparing ? settings.prep : settings.duration;
    const overtime = Boolean(limit) && elapsed >= limit;
    const displayTime = limit ? Math.abs(limit - elapsed) : elapsed;
    label.textContent = preparing ? 'Prep time remaining' :
      overtime ? 'Overtime' : limit ? 'Time remaining' : 'Time elapsed';
    timer.textContent = formatTime(displayTime);
    advance.textContent = preparing ? 'Start speaking now' : 'Finish practice';
  }

  advance.addEventListener('click', () => {
    if (preparing) {
      preparing = false;
      startedAt = performance.now();
      updateTimer();
      return;
    }
    const elapsed = Math.floor((performance.now() - startedAt) / 1000);
    const date = localDateKey();
    if (!dashboard.practiceDays.includes(date)) {
      dashboard.practiceDays.push(date);
      saveDashboard();
    }
    if (recorder && recorder.state !== 'inactive') recorder.stop();
    else if (!recordingStream) recordingSession++;
    show('summary');
    recordingFinished.then(() => {
      const review = screen.querySelector('#recording-review');
      if (review && recordingUrl) {
        review.hidden = false;
        review.querySelector('audio').src = recordingUrl;
      }
    });
    screen.querySelector('#elapsed').textContent = 'Rehearsal time: ' + formatTime(elapsed);
    const retry = screen.querySelector('#practice-again');
    retry.href = '#' + mode;
    retry.addEventListener('click', event => {
      event.preventDefault();
      route();
    });
  });
  updateTimer();
  interval = window.setInterval(updateTimer, 200);
}

function bindSetup(mode) {
  const form = screen.querySelector('form');
  const presentation = mode === 'presentation';
  const picker = form.elements.namedItem(presentation ? 'format' : 'source');
  const customField = form.elements.namedItem(presentation ? 'topic' : 'question');

  const suggestion = presentation ? form.elements.namedItem('suggestion') : null;
  const category = presentation ? form.elements.namedItem('category') : null;

  function suggestTopic() {
    const choices = topics[category.value];
    const alternatives = choices.filter(topic => topic !== suggestion.value);
    suggestion.value = pick(alternatives.length ? alternatives : choices);
  }

  if (presentation) {
    suggestion.addEventListener('input', () => suggestion.setCustomValidity(''));
    category.addEventListener('change', suggestTopic);
    form.querySelector('#another-topic').addEventListener('click', suggestTopic);
    suggestTopic();
  }

  function updateField() {
    const custom = picker.value !== (presentation ? 'random' : 'sample');
    customField.closest('label').hidden = !custom;
    customField.required = custom;
    if (presentation) {
      screen.querySelector('#random-settings').hidden = custom;
      suggestion.required = !custom;
    }
    customField.setCustomValidity('');
  }

  picker.addEventListener('change', updateField);
  customField.addEventListener('input', () => customField.setCustomValidity(''));
  updateField();

  form.addEventListener('submit', event => {
    event.preventDefault();
    const data = new FormData(form);
    const customPrompt = customField.value.trim();
    if (customField.required && !customPrompt) {
      customField.setCustomValidity('Enter text before starting.');
      customField.reportValidity();
      return;
    }
    if (suggestion?.required && !suggestion.value.trim()) {
      suggestion.setCustomValidity('Enter a topic before starting.');
      suggestion.reportValidity();
      return;
    }
    const slides = data.get('slides');
    if (slides?.size && !(/\.pdf$/i.test(slides.name) &&
      (!slides.type || slides.type === 'application/pdf'))) {
      const fileInput = form.elements.namedItem('slides');
      fileInput.setCustomValidity('Choose a PDF file.');
      fileInput.reportValidity();
      return;
    }

    startPractice(mode, {
      prompt: customField.required ? customPrompt : presentation ? suggestion.value.trim() : pick(questions),
      prep: Number(data.get('prep')),
      duration: Number(data.get('duration')),
      audience: data.get('audience'),
      style: data.get('style'),
      difficulty: data.get('difficulty'),
      slides
    });
  });

  form.elements.namedItem('slides')?.addEventListener('change', event => {
    event.target.setCustomValidity('');
  });
}

function route() {
  const requested = location.hash.slice(1);
  const mode = ['presentation', 'interview', 'roadmap'].includes(requested) ? requested : 'home';
  show(mode);
  for (const link of document.querySelectorAll('nav a')) {
    if (link.hash === '#' + mode) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  }
  if (mode === 'home') bindHome();
  else if (mode === 'roadmap') bindRoadmap();
  else bindSetup(mode);
}

for (const link of document.querySelectorAll('.bottom-nav a')) {
  link.addEventListener('click', () => {
    if (location.hash === link.hash) route();
  });
}
window.addEventListener('hashchange', route);
route();
