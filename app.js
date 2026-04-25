/*
  Prosty rendering pytań i obsługa formularza.
  Bez frameworków, tylko DOM API.
*/

const form = document.getElementById('underwriting-form');
const baseContainer = document.getElementById('base-questions');
const branchContainer = document.getElementById('branch-questions');

function renderField(question) {
  const wrapper = document.createElement('div');
  wrapper.className = 'field';

  const label = document.createElement('label');
  label.setAttribute('for', question.key);
  label.textContent = question.label;

  let input;

  if (question.type === 'select') {
    input = document.createElement('select');
    if (question.key === 'dzialalnosc') {
      const empty = document.createElement('option');
      empty.value = '';
      empty.textContent = 'Wybierz';
      input.appendChild(empty);

      window.QUESTION_ENGINE.industries.forEach((industry) => {
        const option = document.createElement('option');
        option.value = industry.value;
        option.textContent = industry.label;
        option.disabled = Boolean(industry.excluded);
        input.appendChild(option);
      });
    } else {
      question.options.forEach((opt) => {
        const option = document.createElement('option');
        option.value = opt;
        option.textContent = opt;
        input.appendChild(option);
      });
    }
  } else if (question.type === 'yesno') {
    input = document.createElement('select');
    ['nie', 'tak'].forEach((v) => {
      const option = document.createElement('option');
      option.value = v;
      option.textContent = v;
      input.appendChild(option);
    });
  } else if (question.type === 'text') {
    input = document.createElement('textarea');
  } else {
    input = document.createElement('input');
    input.type = 'number';
    input.min = '0';
  }

  input.id = question.key;
  input.name = question.key;

  wrapper.appendChild(label);
  wrapper.appendChild(input);
  return wrapper;
}

function renderBaseQuestions() {
  baseContainer.innerHTML = '<h2>Pytania podstawowe</h2>';
  window.QUESTION_ENGINE.baseQuestions.forEach((question) => {
    baseContainer.appendChild(renderField(question));
  });
}

function renderBranchQuestions(formData) {
  branchContainer.innerHTML = '<h2>Pytania dodatkowe</h2>';

  const activeBranches = window.getActiveBranches(formData);
  if (activeBranches.length === 0) {
    const info = document.createElement('p');
    info.className = 'muted';
    info.textContent = 'Brak dodatkowych pytań dla wybranej konfiguracji.';
    branchContainer.appendChild(info);
    return;
  }

  activeBranches.forEach((branch) => {
    const questions = window.QUESTION_ENGINE.branchQuestions[branch] || [];
    questions.forEach((question) => {
      branchContainer.appendChild(renderField(question));
    });
  });
}

function getFormData() {
  const data = {};
  const fields = form.querySelectorAll('input, select, textarea');

  fields.forEach((field) => {
    data[field.name] = field.value;
  });

  return data;
}

function showResult(result) {
  document.getElementById('result').hidden = false;
  document.getElementById('out-industry').textContent = result.industry_group;
  document.getElementById('out-model').textContent = result.selected_model;
  document.getElementById('out-risks').textContent = result.risk_flags.length
    ? result.risk_flags.join(', ')
    : 'Brak';
  document.getElementById('out-coverages').textContent = result.coverages.join(', ');
  document.getElementById('out-referral').textContent = result.refer_to_underwriter ? 'TAK' : 'NIE';
}

form.addEventListener('change', () => {
  renderBranchQuestions(getFormData());
});

form.addEventListener('submit', (event) => {
  event.preventDefault();
  const data = getFormData();
  const result = window.evaluateCase(data);
  showResult(result);
});

renderBaseQuestions();
renderBranchQuestions(getFormData());
