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
  const profile = screen.querySelector('#edit-profile');
  profile.textContent = name ? [...name][0].toUpperCase() : 'S';
  if (dashboard.avatar) {
    const photo = document.createElement('img');
    photo.src = dashboard.avatar;
    photo.alt = '';
    profile.replaceChildren(photo);
  }
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
    if (practiced && isToday) item.classList.add('practiced');
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
  screen.querySelector('#edit-profile').addEventListener('click', () => { location.hash = '#account'; });

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

function bindAccount() {
  const form = screen.querySelector('#account-form');
  const fields = ['name', 'username', 'email', 'phone', 'recoveryEmail'];
  const status = screen.querySelector('#account-status');
  const avatar = screen.querySelector('#avatar-image');
  const initial = screen.querySelector('#avatar-initial');
  const photoInput = screen.querySelector('#avatar-file');
  let pendingAvatar = dashboard.avatar || '';

  for (const name of fields) form.elements[name].value = dashboard[name] || '';

  function updateAvatar() {
    initial.textContent = (form.elements.name.value.trim()[0] || 'S').toUpperCase();
    avatar.hidden = !pendingAvatar;
    initial.hidden = Boolean(pendingAvatar);
    if (pendingAvatar) avatar.src = pendingAvatar;
    else avatar.removeAttribute('src');
  }

  form.elements.name.addEventListener('input', updateAvatar);
  photoInput.addEventListener('change', () => {
    const file = photoInput.files[0];
    if (!file) return;
    if ((dashboard.privacy?.photo || 'none') === 'none') {
      status.textContent = 'Enable photo access in Privacy before choosing a photo.';
      photoInput.value = '';
      return;
    }
    if (!file.type.startsWith('image/') || file.size > 1024 * 1024) {
      status.textContent = 'Choose an image under 1 MB.';
      photoInput.value = '';
      return;
    }
    const reader = new FileReader();
    reader.addEventListener('load', () => {
      pendingAvatar = reader.result;
      screen.querySelector('#crop-controls').hidden = false;
      updateAvatar();
    });
    reader.readAsDataURL(file);
  });
  const zoom = screen.querySelector('#crop-zoom');
  const cropX = screen.querySelector('#crop-x');
  const cropY = screen.querySelector('#crop-y');
  function previewCrop() {
    avatar.style.transform = 'scale(' + zoom.value + ')';
    avatar.style.objectPosition = cropX.value + '% ' + cropY.value + '%';
  }
  for (const control of [zoom, cropX, cropY]) control.addEventListener('input', previewCrop);
  screen.querySelector('#crop-apply').addEventListener('click', () => {
    const img = new Image();
    img.onload = () => {
      const base = Math.min(img.width, img.height) / Number(zoom.value);
      const x = (img.width - base) * Number(cropX.value) / 100;
      const y = (img.height - base) * Number(cropY.value) / 100;
      const canvas = document.createElement('canvas');
      canvas.width = 256; canvas.height = 256;
      canvas.getContext('2d').drawImage(img, x, y, base, base, 0, 0, 256, 256);
      pendingAvatar = canvas.toDataURL('image/png');
      avatar.style.transform = '';
      avatar.style.objectPosition = '';
      screen.querySelector('#crop-controls').hidden = true;
      updateAvatar();
      status.textContent = 'Photo adjusted. Save changes to keep it.';
    };
    img.src = pendingAvatar;
  });
  screen.querySelector('#remove-avatar').addEventListener('click', () => {
    pendingAvatar = '';
    screen.querySelector('#crop-controls').hidden = true;
    avatar.style.transform = '';
    photoInput.value = '';
    updateAvatar();
  });
  form.addEventListener('submit', event => {
    event.preventDefault();
    const next = { ...dashboard, avatar: pendingAvatar };
    for (const name of fields) next[name] = form.elements[name].value.trim();
    try {
      localStorage.setItem(storageKey, JSON.stringify(next));
      dashboard = next;
      status.textContent = 'Saved on this device.';
    } catch {
      status.textContent = 'Could not save. Check browser storage or choose a smaller photo.';
    }
  });
  updateAvatar();
}

function bindPrivacy() {
  const privacy = dashboard.privacy || { microphone: false, camera: false, photo: 'none' };
  for (const name of ['microphone', 'camera']) {
    const control = screen.querySelector('#' + name + '-access');
    control.checked = Boolean(privacy[name]);
    control.addEventListener('change', () => {
      privacy[name] = control.checked;
      dashboard.privacy = privacy;
      saveDashboard();
    });
  }
  const photo = screen.querySelector('#photo-access');
  photo.value = privacy.photo || 'none';
  photo.addEventListener('change', () => {
    privacy.photo = photo.value;
    dashboard.privacy = privacy;
    saveDashboard();
  });
}

const landmarks = [
  { name: 'Statue of Liberty', region: 'USA', skill: 'Pacing', prompts: ['Introduce yourself at a comfortable pace.', 'Describe a place you enjoy visiting.', 'Explain a daily routine with a pause between ideas.'] },
  { name: 'Golden Gate Bridge', region: 'USA', skill: 'Pacing', prompts: ['Explain a hobby in three sentences.', 'Describe a memorable trip with natural pauses.', 'Tell a short story without rushing.'] },
  { name: 'Mount Rushmore', region: 'USA', skill: 'Pacing', prompts: ['Explain a challenge you overcame.', 'Describe your favorite subject.', 'Summarize a story in one minute.'] },
  { name: 'Eiffel Tower', region: 'Europe', skill: 'Clarity', prompts: ['Explain an idea to someone new to it.', 'Describe a useful tool.', 'Give directions to a familiar place.'] },
  { name: 'Big Ben', region: 'Europe', skill: 'Clarity', prompts: ['Explain a simple process.', 'Describe your favorite meal.', 'Explain why a place matters to you.'] },
  { name: 'Colosseum', region: 'Europe', skill: 'Clarity', prompts: ['Describe a team experience.', 'Explain a rule for a game.', 'Summarize a book or show.'] },
  { name: 'Taj Mahal', region: 'India', skill: 'Structure', prompts: ['Share an idea with a beginning, middle, and end.', 'Describe a goal and how you plan to reach it.', 'Give an example that supports an opinion.'] },
  { name: 'India Gate', region: 'India', skill: 'Structure', prompts: ['Explain a problem and a solution.', 'Describe a project in three steps.', 'Share a lesson you learned.'] },
  { name: 'Hawa Mahal', region: 'India', skill: 'Structure', prompts: ['Tell a short story with a takeaway.', 'Compare two activities.', 'Explain a choice and your reasons.'] }
];

function isRoadmapUnlocked(index) {
  const completed = Array.isArray(dashboard.roadmapCompleted) ? dashboard.roadmapCompleted : [];
  if (index === 0) return true;
  const previousRegionEnd = Math.floor(index / 3) * 3;
  return completed.includes(index - 1) &&
    Array.from({ length: previousRegionEnd }, (_, step) => step).every(step => completed.includes(step));
}

function travelerSprite(id) {
  const sprite = document.createElement('span');
  sprite.className = 'character-sprite';
  sprite.style.backgroundPosition = ((id % 3) * 50) + '% ' + (id < 3 ? '0%' : '100%');
  sprite.setAttribute('aria-hidden', 'true');
  return sprite;
}

function bindRoadmap() {
  const map = screen.querySelector('#map-frame');
  const canvas = screen.querySelector('#map-canvas');
  let drag = null;
  map.addEventListener('pointerdown', event => {
    if (event.pointerType === 'touch' || event.target.closest('button')) return;
    drag = { y: event.clientY, top: map.scrollTop };
    map.setPointerCapture(event.pointerId);
    map.classList.add('dragging');
  });
  map.addEventListener('pointermove', event => {
    if (drag) map.scrollTop = drag.top - (event.clientY - drag.y);
  });
  const stopDrag = () => { drag = null; map.classList.remove('dragging'); };
  map.addEventListener('pointerup', stopDrag);
  map.addEventListener('pointercancel', stopDrag);
  const completed = Array.isArray(dashboard.roadmapCompleted) ? dashboard.roadmapCompleted : [];
  const characterDialog = screen.querySelector('#character-dialog');
  const characterOptions = screen.querySelector('#character-options');
  for (let id = 0; id < 6; id++) {
    const choice = document.createElement('button');
    choice.type = 'button';
    choice.className = 'character-choice';
    const outfit = id < 3 ? 'Pink cardigan' : 'Navy vest';
    const tone = ['light', 'medium', 'dark'][id % 3];
    choice.setAttribute('aria-label', outfit + ', ' + tone + ' skin tone');
    choice.append(travelerSprite(id));
    choice.addEventListener('click', () => {
      dashboard.roadmapCharacter = id;
      saveDashboard();
      characterDialog.close();
      route();
    });
    characterOptions.append(choice);
  }
  screen.querySelector('#character-change').addEventListener('click', () => characterDialog.showModal());
  if (!Number.isInteger(dashboard.roadmapCharacter)) characterDialog.showModal();
  screen.querySelector('#completed-count').textContent = completed.length + ' / 9';

  for (let region = 0; region < 3; region++) {
    const area = document.createElement('section');
    area.className = 'map-region region-' + region;
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 360 720');
    svg.setAttribute('preserveAspectRatio', 'none');
    svg.setAttribute('aria-hidden', 'true');
    svg.classList.add('travel-road');
    for (const className of ['travel-road-edge', 'travel-road-dash']) {
      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('d', 'M180 -20 C180 70 300 75 270 165 S65 245 90 335 S300 410 270 500 S80 580 180 740');
      path.setAttribute('class', className);
      svg.append(path);
    }
    area.append(svg);
    const title = document.createElement('h2');
    title.textContent = ['USA · Pacing', 'Europe · Clarity', 'India · Structure'][region];
    area.append(title);
    const regionLocked = region > 0 && !Array.from({ length: region * 3 }, (_, step) => step).every(step => completed.includes(step));
    if (regionLocked) {
      area.classList.add('region-locked');
      const overlay = document.createElement('div');
      overlay.className = 'region-overlay';
      overlay.setAttribute('aria-label', 'Region locked. Complete the earlier stops.');
      const regionLock = document.createElement('span');
      regionLock.className = 'pixel-lock';
      regionLock.setAttribute('aria-hidden', 'true');
      overlay.append(regionLock);
      area.append(overlay);
    }
    for (let slot = 0; slot < 3; slot++) {
      const index = region * 3 + slot;
      const place = landmarks[index];
      const button = document.createElement('button');
      button.className = 'landmark stop-' + slot;
      button.type = 'button';
      const unlocked = isRoadmapUnlocked(index) || completed.includes(index);
      button.disabled = !unlocked;
      button.setAttribute('aria-label', place.name + ', ' + place.region + (completed.includes(index) ? ', completed' : unlocked ? ', unlocked' : ', locked'));
      const art = document.createElement('span');
      art.className = 'landmark-art';
      art.style.backgroundPosition = (slot * 50) + '% ' + (region * 50) + '%';
      const label = document.createElement('span');
      label.className = 'landmark-label';
      label.textContent = place.name + ' · ' + ['Easy', 'Medium', 'Hard'][slot];
      button.append(art, label);
      if (!unlocked) {
        const lock = document.createElement('span');
        lock.className = 'stop-lock';
        lock.append(document.createElement('span'));
        lock.firstChild.className = 'pixel-lock';
        lock.setAttribute('aria-hidden', 'true');
        button.append(lock);
      }
      if (dashboard.roadmapLocation === index || (dashboard.roadmapLocation == null && index === 0)) {
        const marker = document.createElement('span');
        marker.className = 'travel-marker';
        marker.append(travelerSprite(Number.isInteger(dashboard.roadmapCharacter) ? dashboard.roadmapCharacter : 0));
        marker.setAttribute('aria-hidden', 'true');
        button.append(marker);
      }
      button.addEventListener('click', () => {
        dashboard.roadmapLocation = index;
        saveDashboard();
        location.hash = '#section-' + index;
      });
      area.append(button);
    }
    canvas.append(area);
  }
  const selected = canvas.querySelector('.travel-marker');
  if (selected) {
    selected.closest('button').scrollIntoView({ block: 'nearest' });
    window.scrollTo(0, 0);
  }
}

const roadmapQuizzes = {
  Pacing: [
    ['What can help listeners follow a longer answer?', ['Pause between main ideas', 'Rush through every sentence', 'Avoid taking breaths'], 0],
    ['If you lose your place, what is a helpful next step?', ['Take a moment and continue', 'Stop speaking permanently', 'Repeat every word as fast as possible'], 0],
    ['How can you practice a comfortable pace?', ['Record a short answer and listen back', 'Use one speed for every situation', 'Never pause while thinking'], 0]
  ],
  Clarity: [
    ['What can make an unfamiliar idea easier to understand?', ['Use a familiar example', 'Add unrelated details', 'Skip the main point'], 0],
    ['When explaining a process, what helps a listener?', ['Present the steps in order', 'Start with unrelated facts', 'Leave out the purpose'], 0],
    ['How can you check whether your explanation was clear?', ['Ask a listener what they understood', 'Assume everyone understood', 'Change the topic immediately'], 0]
  ],
  Structure: [
    ['What is a useful way to organize a short answer?', ['Main idea, example, takeaway', 'Details with no main idea', 'Conclusion before choosing a topic'], 0],
    ['What can support an opinion?', ['A relevant example and a reason', 'An unrelated story', 'Repeating the opinion only'], 0],
    ['How can you end a longer explanation?', ['Summarize the main point', 'Introduce several unrelated ideas', 'Leave the sentence unfinished'], 0]
  ]
};

const advancedRoadmapQuizzes = {
  Pacing: [
    [
      ['Your answer has three ideas. Where could you pause?', ['Between the ideas', 'Only after every word', 'Never'], 0],
      ['A listener asks you to slow down. What can you try?', ['Pause briefly and use shorter phrases', 'Ignore the listener', 'Stop taking breaths'], 0],
      ['How could you compare two recordings?', ['Listen to similar answers and notice pauses', 'Judge your personality from speed', 'Use only the longer recording'], 0]
    ],
    [
      ['A technical point needs emphasis. What might help?', ['Pause before and after the key point', 'Speed through the key point', 'Remove all pauses'], 0],
      ['Your audience looks confused during a fast explanation. What can you do?', ['Pause, rephrase and check in', 'Speak even faster', 'Continue without checking'], 0],
      ['What is a good pacing goal for a practice session?', ['Choose a pace that fits your audience and message', 'Use exactly the same speed in every setting', 'Treat all pauses as mistakes'], 0]
    ]
  ],
  Clarity: [
    [
      ['An audience is unfamiliar with a term. What helps?', ['Define it in everyday language', 'Repeat the term without explanation', 'Move on immediately'], 0],
      ['Your explanation has too many details. What should you do first?', ['Identify the main point', 'Add more unrelated examples', 'Speak more quietly'], 0],
      ['How can an example support a difficult idea?', ['Connect it directly to the idea', 'Use a random example', 'Avoid explaining the connection'], 0]
    ],
    [
      ['A listener misunderstands an instruction. What next?', ['Rephrase and ask what needs clarification', 'Repeat it faster', 'Blame the listener'], 0],
      ['How can you make a complex comparison clear?', ['Use a shared point of comparison', 'Switch topics between items', 'Remove all context'], 0],
      ['When adapting to an audience, what matters?', ['Their familiarity with the topic', 'Using as many technical terms as possible', 'Giving everyone identical detail'], 0]
    ]
  ],
  Structure: [
    [
      ['For a problem-solving answer, what sequence works?', ['Problem, action, result', 'Result, unrelated story, problem', 'Only the problem'], 0],
      ['What makes an example useful in an answer?', ['It supports the main point', 'It changes the topic', 'It replaces the answer entirely'], 0],
      ['How can you transition between ideas?', ['Use a phrase showing their connection', 'Switch without context', 'Repeat the opening indefinitely'], 0]
    ],
    [
      ['You have several points and limited time. How should you plan?', ['Prioritize the points supporting your purpose', 'Give unrelated details equal time', 'Skip the main point'], 0],
      ['How can you connect a story to an interview question?', ['Explain the relevant result and lesson', 'End without connecting it', 'Describe unrelated events only'], 0],
      ['How can you revise a disorganized answer?', ['Identify the main point and reorder supporting details', 'Add details without a plan', 'Remove every example'], 0]
    ]
  ]
};

function bindSection(index) {
  const place = landmarks[index];
  const completed = Array.isArray(dashboard.roadmapCompleted) ? dashboard.roadmapCompleted : [];
  if (!place || (!isRoadmapUnlocked(index) && !completed.includes(index)) || !Number.isInteger(dashboard.roadmapCharacter)) {
    location.hash = '#roadmap';
    return;
  }
  screen.querySelector('#section-region').textContent = place.region + ' · ' + place.skill + ' · ' + ['Easy', 'Medium', 'Hard'][index % 3];
  screen.querySelector('#section-title').textContent = place.name;
  const container = screen.querySelector('#section-questions');
  const form = screen.querySelector('#section-form');
  const feedback = screen.querySelector('#section-feedback');
  const difficulty = index % 3;
  const questions = difficulty === 0 ? roadmapQuizzes[place.skill] : advancedRoadmapQuizzes[place.skill][difficulty - 1];
  let questionIndex = 0;

  function renderQuestion() {
    screen.querySelector('#quiz-step').textContent = 'Question ' + (questionIndex + 1) + ' of ' + questions.length;
    feedback.textContent = '';
    container.replaceChildren();
    const [question, options] = questions[questionIndex];
    const legend = document.createElement('legend');
    legend.textContent = question;
    container.append(legend);
    options.forEach((option, i) => {
      const label = document.createElement('label');
      label.className = 'quiz-option';
      const input = document.createElement('input');
      input.type = 'radio'; input.name = 'answer'; input.value = String(i); input.required = true;
      label.append(input, document.createTextNode(option));
      container.append(label);
    });
    screen.querySelector('#quiz-next').textContent = questionIndex === questions.length - 1 ? 'Finish section' : 'Next question';
  }
  form.addEventListener('submit', event => {
    event.preventDefault();
    const chosen = form.querySelector('input[name="answer"]:checked');
    if (!chosen) return;
    if (Number(chosen.value) !== questions[questionIndex][2]) {
      feedback.textContent = 'Try another answer.';
      return;
    }
    if (questionIndex < questions.length - 1) {
      questionIndex++;
      renderQuestion();
      return;
    }
    dashboard.roadmapCompleted ||= [];
    if (!dashboard.roadmapCompleted.includes(index)) dashboard.roadmapCompleted.push(index);
    dashboard.roadmapLocation = Math.min(index + 1, landmarks.length - 1);
    saveDashboard();
    location.hash = '#roadmap';
  });
  renderQuestion();
}

function bindRetake() {
  const questions = [
    'Which speaking situation would you like to practice?',
    'What would you most like to work on?',
    'How comfortable do you feel speaking to a group?',
    'How much structure would you like in practice?',
    'What kind of prompt would you prefer?'
  ];
  const options = [
    ['Presentations', 'Interviews', 'Everyday speaking'],
    ['Pacing', 'Clarity', 'Structure', 'Fluency'],
    ['Not yet comfortable', 'Somewhat comfortable', 'Comfortable'],
    ['Step-by-step guidance', 'Some guidance', 'Open practice'],
    ['Familiar topics', 'A mix', 'New challenges']
  ];
  const container = screen.querySelector('#retake-questions');
  questions.forEach((question, i) => {
    const label = document.createElement('label'); label.textContent = question;
    const select = document.createElement('select'); select.required = true;
    select.add(new Option('Choose an answer', ''));
    options[i].forEach(option => select.add(new Option(option, option)));
    select.value = dashboard.retakeAnswers?.[i] || '';
    label.append(select); container.append(label);
  });
  screen.querySelector('#retake-form').addEventListener('submit', event => {
    event.preventDefault();
    dashboard.retakeAnswers = [...container.querySelectorAll('select')].map(select => select.value);
    saveDashboard();
    screen.querySelector('#quiz-status').textContent = 'Answers saved on this device.';
  });
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
      if (!dashboard.privacy?.microphone) {
        status.textContent = 'Turn on microphone access in Privacy to record.';
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
  const sectionMatch = /^section-([0-8])$/.exec(requested);
  const mode = sectionMatch ? 'section-practice' : ['presentation', 'interview', 'roadmap', 'account', 'settings', 'privacy', 'retake'].includes(requested) ? requested : 'home';
  show(mode);
  document.querySelector('.bottom-nav').hidden = ['account', 'settings', 'privacy', 'section-practice', 'retake'].includes(mode);
  for (const link of document.querySelectorAll('nav a')) {
    if (link.hash === '#' + mode) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  }
  if (mode === 'home') bindHome();
  else if (mode === 'roadmap') bindRoadmap();
  else if (mode === 'account') bindAccount();
  else if (mode === 'privacy') bindPrivacy();
  else if (mode === 'section-practice') bindSection(Number(sectionMatch[1]));
  else if (mode === 'retake') bindRetake();
  else if (mode !== 'settings') bindSetup(mode);
}

for (const link of document.querySelectorAll('.bottom-nav a')) {
  link.addEventListener('click', () => {
    if (location.hash === link.hash) route();
  });
}
window.addEventListener('hashchange', route);
route();

let displayedDate = localDateKey();
window.setInterval(() => {
  if (location.hash !== '' && location.hash !== '#home') return;
  const currentDate = localDateKey();
  if (currentDate !== displayedDate) {
    displayedDate = currentDate;
    route();
  }
}, 60000);
document.addEventListener('visibilitychange', () => {
  if (!document.hidden && (!location.hash || location.hash === '#home') && localDateKey() !== displayedDate) {
    displayedDate = localDateKey();
    route();
  }
});
