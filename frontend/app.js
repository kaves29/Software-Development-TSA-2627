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
let dashboard = { name: '', goal: '', practiceDays: [], focus: [], improved: [], sessions: null };

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
  const todayDate = new Date();
  screen.querySelector('#today-date').textContent = new Intl.DateTimeFormat(undefined, {
    weekday: 'long', month: 'long', day: 'numeric'
  }).format(todayDate);
  const weekStart = new Date(todayDate.getFullYear(), todayDate.getMonth(), todayDate.getDate());
  weekStart.setDate(weekStart.getDate() - (weekStart.getDay() + 6) % 7);
  const weekStrip = screen.querySelector('#week-strip');
  weekStrip.replaceChildren();
  for (let offset = 0; offset < 7; offset++) {
    const day = new Date(weekStart);
    day.setDate(weekStart.getDate() + offset);
    const dateKey = localDateKey(day);
    const practiced = dashboard.practiceDays.includes(dateKey);
    const isToday = dateKey === localDateKey(todayDate);
    const item = document.createElement('li');
    item.className = 'week-day';
    if (practiced) item.classList.add('practiced');
    if (isToday) item.classList.add('today');
    if (dateKey < localDateKey(todayDate)) item.classList.add('past');
    const label = new Intl.DateTimeFormat(undefined, { weekday: 'short' }).format(day);
    const fullDate = new Intl.DateTimeFormat(undefined, { weekday: 'long', month: 'long', day: 'numeric' }).format(day);
    item.setAttribute('aria-label', fullDate + (isToday ? ', today' : '') + (practiced ? ', practiced' : ', no practice recorded'));
    const circle = document.createElement('span');
    circle.className = 'week-dot';
    circle.textContent = String(day.getDate());
    const dayName = document.createElement('span');
    dayName.className = 'week-day-name';
    dayName.textContent = label;
    item.append(circle, dayName);
    weekStrip.append(item);
  }
  screen.querySelector('#improved-skills').textContent = dashboard.improved.length
    ? dashboard.improved.join(', ') + ' · Self-reported'
    : 'Track improvements in your roadmap.';

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
  if (!Array.isArray(dashboard.goals)) {
    dashboard.goals = [{ name: 'Your goal', date: dashboard.goal || '' }];
  }
  if (!Array.isArray(dashboard.sessions)) {
    dashboard.sessions = [
      { name: 'Session 1', type: '', description: '' },
      { name: 'Session 2', type: '', description: '' }
    ];
  }
  const today = localDateKey();
  for (const session of dashboard.sessions) {
    if (!session.date) session.date = today;
  }
  if (!Array.isArray(dashboard.skillLevels)) {
    dashboard.skillLevels = ['Pacing', 'Clarity', 'Structure'].map(name => ({ name, value: 0 }));
  }
  saveDashboard();
  updateHome();
  bindDashboardDialog('#profile-dialog', '#edit-profile', 'displayName', 'name');

  let goalIndex = 0;
  const goalDialog = screen.querySelector('#goal-dialog');
  const goalForm = goalDialog.querySelector('form');

  function renderGoal() {
    const goal = dashboard.goals[goalIndex];
    screen.querySelector('.goal-label').textContent = goal ? goal.name || 'Your goal' : 'Add a goal';
    const value = screen.querySelector('#goal-value');
    const caption = screen.querySelector('#goal-caption');
    if (!goal) {
      value.textContent = '+';
      caption.textContent = 'Set another goal';
    } else if (!goal.date) {
      value.textContent = '—';
      caption.textContent = 'Tap to set a date';
    } else {
      const days = Math.round((Date.parse(goal.date) - Date.parse(localDateKey())) / 86400000);
      value.textContent = days > 0 ? String(days) : days === 0 ? '0' : '—';
      caption.textContent = days > 0 ? (days === 1 ? 'day to go' : 'days to go') : days === 0 ? 'Goal day' : 'Goal date passed';
    }
    screen.querySelector('#goal-position').textContent = goal ? (goalIndex + 1) + ' / ' + dashboard.goals.length : 'Add a goal';
    screen.querySelector('#goal-prev').disabled = goalIndex === 0;
    screen.querySelector('#goal-next').disabled = goalIndex >= dashboard.goals.length - (dashboard.goals.length >= 3 ? 1 : 0);
    screen.querySelector('#goal-next').hidden = goalIndex >= dashboard.goals.length;
  }

  screen.querySelector('#goal-prev').addEventListener('click', () => { goalIndex--; renderGoal(); });
  screen.querySelector('#goal-next').addEventListener('click', () => { goalIndex++; renderGoal(); });
  screen.querySelector('#edit-goal').addEventListener('click', () => {
    const goal = dashboard.goals[goalIndex];
    goalForm.elements.goalName.value = goal?.name || '';
    goalForm.elements.target.value = goal?.date || '';
    goalDialog.returnValue = '';
    goalDialog.showModal();
  });
  goalDialog.addEventListener('close', () => {
    if (goalDialog.returnValue === 'save') {
      const goal = { name: goalForm.elements.goalName.value.trim() || 'Your goal', date: goalForm.elements.target.value };
      if (goalIndex === dashboard.goals.length && dashboard.goals.length < 3) dashboard.goals.push(goal);
      else dashboard.goals[goalIndex] = goal;
    } else if (goalDialog.returnValue === 'remove' && dashboard.goals[goalIndex]) {
      dashboard.goals[goalIndex].date = '';
      dashboard.goals[goalIndex].name = 'Your goal';
    }
    saveDashboard();
    renderGoal();
  });
  let touchStartX = 0;
  screen.querySelector('.goal-carousel').addEventListener('touchstart', event => { touchStartX = event.changedTouches[0].clientX; }, { passive: true });
  screen.querySelector('.goal-carousel').addEventListener('touchend', event => {
    const delta = event.changedTouches[0].clientX - touchStartX;
    if (delta > 50 && goalIndex > 0) goalIndex--;
    if (delta < -50 && goalIndex < dashboard.goals.length && dashboard.goals.length < 3) goalIndex++;
    else if (delta < -50 && goalIndex < dashboard.goals.length - 1) goalIndex++;
    renderGoal();
  }, { passive: true });
  renderGoal();

  let selectedDate = today;
  const list = screen.querySelector('#session-list');
  const addButton = screen.querySelector('#add-session');
  const limitMessage = screen.querySelector('#session-limit');
  const dialog = screen.querySelector('#session-dialog');
  const form = screen.querySelector('#session-form');
  let editingIndex = -1;

  function renderSessions() {
    const matching = dashboard.sessions.map((session, index) => ({ session, index }))
      .filter(({ session }) => session.date === selectedDate)
      .sort((a, b) => (a.session.startTime || '99').localeCompare(b.session.startTime || '99'));
    const date = new Date(selectedDate + 'T12:00:00');
    screen.querySelector('#practice-heading').textContent = new Intl.DateTimeFormat(undefined, {weekday:'long', month:'short', day:'numeric'}).format(date);
    screen.querySelector('#today-date').textContent = matching.filter(({session}) => session.done).length + '/' + matching.length + ' completed';
    list.replaceChildren();
    const timeGroups = new Map();
    for (const { session, index } of matching) {
      const row = document.createElement('div');
      row.className = 'session-line';
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'session-row';
      button.textContent = session.name;
      const isPast = session.date < localDateKey();
      button.addEventListener('click', () => openSession(index));
      const check = document.createElement('input');
      check.type = 'checkbox';
      check.className = 'session-check';
      check.checked = Boolean(session.done);
      check.disabled = isPast;
      check.setAttribute('aria-label', 'Mark ' + session.name + ' complete');
      check.addEventListener('change', () => {
        if (session.date < localDateKey()) { renderSessions(); return; }
        session.done = check.checked; saveDashboard(); renderSessions();
      });
      const card = document.createElement('div');
      card.className = 'session-card';
      card.append(button, check);
      const time = document.createElement('div');
      time.className = 'session-time';
      const timeKey = session.startTime ? session.startTime + (session.endTime ? '–' + session.endTime : '') : '';
      if (timeKey && timeGroups.has(timeKey)) {
        timeGroups.get(timeKey).querySelector('.session-group-cards').append(card);
        continue;
      }
      const cards = document.createElement('div');
      cards.className = 'session-group-cards';
      cards.append(card);
      if (timeKey) {
        time.textContent = timeKey;
        timeGroups.set(timeKey, row);
      } else {
        time.hidden = true;
        row.classList.add('untimed');
      }
      row.append(cards, time);
      list.append(row);
    }
    const isPast = selectedDate < localDateKey();
    addButton.hidden = isPast || matching.length >= 5;
    limitMessage.hidden = !isPast && matching.length < 5;
    limitMessage.textContent = isPast ? 'Past sessions are view-only.' : 'Maximum of five sessions';
  }

  function openSession(index) {
    editingIndex = index;
    const session = dashboard.sessions[index];
    const isPast = session.date < localDateKey();
    for (const control of form.elements) control.disabled = isPast;
    screen.querySelector('#session-dialog-title').textContent = isPast ? 'Past session' : 'Edit session';
    form.elements.sessionName.value = session.name;
    form.elements.sessionType.value = session.type;
    form.elements.sessionDescription.value = session.description;
    form.elements.sessionDate.setCustomValidity('');
    form.elements.sessionDate.value = session.date;
    form.elements.startTime.value = session.startTime || '';
    form.elements.endTime.value = session.endTime || '';
    dialog.showModal();
  }
  function saveSession() {
    if (editingIndex < 0) return;
    const old = dashboard.sessions[editingIndex];
    if (old.date < localDateKey()) { editingIndex = -1; renderSessions(); return; }
    const requestedDate = form.elements.sessionDate.value || old.date;
    const destinationFull = dashboard.sessions.filter((session, index) => index !== editingIndex && session.date === requestedDate).length >= 5;
    dashboard.sessions[editingIndex] = {
      ...old,
      name: form.elements.sessionName.value.trim() || old.name,
      type: form.elements.sessionType.value,
      description: form.elements.sessionDescription.value.trim(),
      date: destinationFull || requestedDate < localDateKey() ? old.date : requestedDate,
      startTime: form.elements.startTime.value,
      endTime: form.elements.endTime.value
    };
    saveDashboard();
    editingIndex = -1;
    renderSessions();
  }
  addButton.addEventListener('click', () => {
    const count = dashboard.sessions.filter(session => session.date === selectedDate).length;
    if (count >= 5 || selectedDate < localDateKey()) { renderSessions(); return; }
    dashboard.sessions.push({ name: 'Session ' + (count + 1), type: '', description: '', date: selectedDate });
    saveDashboard();
    renderSessions();
    openSession(dashboard.sessions.length - 1);
  });
  dialog.addEventListener('close', saveSession);
  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
  form.elements.sessionDate.addEventListener('change', () => {
    const target = form.elements.sessionDate.value;
    const count = dashboard.sessions.filter((session, index) => index !== editingIndex && session.date === target).length;
    form.elements.sessionDate.setCustomValidity(target < localDateKey() ? 'Choose today or a future date.' : count >= 5 ? 'This date already has five sessions.' : '');
  });
  form.addEventListener('submit', event => {
    if (!form.elements.sessionName.value.trim()) {
      event.preventDefault();
      form.elements.sessionName.setCustomValidity('Enter a session name.');
      form.elements.sessionName.reportValidity();
    }
  });
  form.elements.sessionName.addEventListener('input', () => form.elements.sessionName.setCustomValidity(''));
  screen.querySelector('#delete-session').addEventListener('click', () => {
    if (dashboard.sessions[editingIndex]?.date < localDateKey()) return;
    dashboard.sessions.splice(editingIndex, 1);
    editingIndex = -1;
    saveDashboard();
    dialog.close();
    renderSessions();
  });

  const timeDialog = screen.querySelector('#time-dialog');
  const timeForm = screen.querySelector('#time-form');
  let timeTarget = null;
  for (let hour = 1; hour <= 12; hour++) {
    timeForm.elements.hour.add(new Option(String(hour), String(hour)));
  }
  for (let minute = 0; minute < 60; minute++) {
    const value = String(minute).padStart(2, '0');
    timeForm.elements.minute.add(new Option(value, value));
  }
  for (const field of [form.elements.startTime, form.elements.endTime]) {
    function openTime() {
      timeTarget = field;
      const [hourText, minuteText] = (field.value || '09:00').split(':');
      const hour = Number(hourText);
      timeForm.elements.hour.value = String(hour % 12 || 12);
      timeForm.elements.minute.value = minuteText;
      timeForm.elements.period.value = hour >= 12 ? 'PM' : 'AM';
      timeDialog.returnValue = '';
      timeDialog.showModal();
    }
    field.addEventListener('click', openTime);
    field.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        openTime();
      }
    });
  }
  timeDialog.addEventListener('close', () => {
    if (!timeTarget) return;
    if (timeDialog.returnValue === 'clear') timeTarget.value = '';
    if (timeDialog.returnValue === 'save') {
      const hour = Number(timeForm.elements.hour.value) % 12 + (timeForm.elements.period.value === 'PM' ? 12 : 0);
      timeTarget.value = String(hour).padStart(2, '0') + ':' + timeForm.elements.minute.value;
    }
    timeTarget = null;
  });
  timeDialog.addEventListener('click', event => { if (event.target === timeDialog) timeDialog.close(); });

  const calendar = screen.querySelector('#calendar-dialog');
  let month = new Date();
  let calendarTarget = null;
  function renderCalendar() {
    screen.querySelector('#calendar-title').textContent = new Intl.DateTimeFormat(undefined, {month:'long', year:'numeric'}).format(month);
    const grid = screen.querySelector('#calendar-grid');
    grid.replaceChildren();
    for (const name of ['M', 'T', 'W', 'T', 'F', 'S', 'S']) {
      const label = document.createElement('span'); label.textContent = name; grid.append(label);
    }
    const first = new Date(month.getFullYear(), month.getMonth(), 1);
    for (let i = 0; i < (first.getDay() + 6) % 7; i++) grid.append(document.createElement('span'));
    const days = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
    for (let day = 1; day <= days; day++) {
      const date = new Date(month.getFullYear(), month.getMonth(), day);
      const key = localDateKey(date);
      const button = document.createElement('button');
      button.type = 'button'; button.textContent = String(day);
      button.setAttribute('aria-label', new Intl.DateTimeFormat(undefined, {dateStyle:'full'}).format(date));
      if (key < localDateKey()) button.classList.add('past');
      if (key < localDateKey() && calendarTarget === form.elements.sessionDate) button.disabled = true;
      const activeDate = calendarTarget ? calendarTarget.value : selectedDate;
      if (key === activeDate) button.setAttribute('aria-current', 'date');
      if (key === today) button.classList.add('calendar-today');
      button.addEventListener('click', () => {
        if (calendarTarget) {
          calendarTarget.value = key;
          calendarTarget.dispatchEvent(new Event('change', { bubbles: true }));
        } else {
          selectedDate = key;
          renderSessions();
        }
        calendar.close();
      });
      grid.append(button);
    }
  }
  function openCalendar(target) {
    calendarTarget = target;
    const initialDate = target?.value || selectedDate;
    month = new Date(initialDate + 'T12:00:00');
    renderCalendar();
    calendar.showModal();
  }
  screen.querySelector('#calendar-open').addEventListener('click', () => openCalendar(null));
  form.elements.sessionDate.addEventListener('click', () => openCalendar(form.elements.sessionDate));
  goalForm.elements.target.addEventListener('click', () => openCalendar(goalForm.elements.target));
  for (const field of [form.elements.sessionDate, goalForm.elements.target]) {
    field.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        openCalendar(field);
      }
    });
  }
  goalForm.addEventListener('submit', event => {
    if (event.submitter?.value === 'save' && !goalForm.elements.target.value) {
      event.preventDefault();
      openCalendar(goalForm.elements.target);
    }
  });
  screen.querySelector('#month-prev').addEventListener('click', () => { month.setDate(1); month.setMonth(month.getMonth() - 1); renderCalendar(); });
  screen.querySelector('#month-next').addEventListener('click', () => { month.setDate(1); month.setMonth(month.getMonth() + 1); renderCalendar(); });
  calendar.addEventListener('click', event => { if (event.target === calendar) calendar.close(); });

  const bars = screen.querySelector('#skill-bars');
  dashboard.skillLevels.forEach((skill, index) => {
    const row = document.createElement('div'); row.className = 'skill-bar';
    const name = document.createElement('input'); name.value = skill.name; name.maxLength = 40; name.setAttribute('aria-label', 'Skill ' + (index + 1) + ' name');
    const progress = document.createElement('progress');
    progress.max = 100;
    progress.value = 0;
    progress.setAttribute('aria-label', skill.name + ' progress, 0 percent');
    const output = document.createElement('output'); output.textContent = '0%';
    name.addEventListener('change', () => {
      skill.name = name.value.trim() || skill.name;
      name.value = skill.name;
      progress.setAttribute('aria-label', skill.name + ' progress, 0 percent');
      saveDashboard();
    });
    row.append(name, progress, output); bars.append(row);
  });
  renderSessions();
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
