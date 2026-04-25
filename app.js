/*
  Prosty rendering pytań i obsługa formularza.
  Bez frameworków, tylko DOM API.
*/

const form = document.getElementById('underwriting-form');
const baseContainer = document.getElementById('base-questions');
const branchContainer = document.getElementById('branch-questions');
const validationContainer = document.getElementById('validation-errors');

function addPlaceholderOption(select, text) {
  const option = document.createElement('option');
  option.value = '';
  option.textContent = text;
  select.appendChild(option);
}

function renderField(question) {
  const wrapper = document.createElement('div');
  wrapper.className = 'field';

  const label = document.createElement('label');
  label.setAttribute('for', question.key);
  label.textContent = question.label;

  if (question.required) {
    const reqMark = document.createElement('span');
    reqMark.className = 'required-mark';
    reqMark.textContent = ' *';
    label.appendChild(reqMark);
  }

  let input;

  if (question.type === 'select') {
    input = document.createElement('select');
    addPlaceholderOption(input, 'Wybierz');

    if (question.key === 'dzialalnosc') {
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
  } else if (question.type === 'multiselect') {
    input = document.createElement('select');
    input.multiple = true;
    input.size = Math.min(question.options.length, 8);

    question.options.forEach((opt) => {
      const option = document.createElement('option');
      option.value = opt;
      option.textContent = opt;
      input.appendChild(option);
    });
  } else if (question.type === 'yesno') {
    input = document.createElement('select');
    addPlaceholderOption(input, 'Wybierz');
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

  if (question.unitHint) {
    const unit = document.createElement('div');
    unit.className = 'field-unit';
    unit.textContent = `Jednostka: ${question.unitHint}`;
    wrapper.appendChild(unit);
  }

  wrapper.appendChild(input);

  if (question.helperText) {
    const helper = document.createElement('div');
    helper.className = 'field-helper';
    helper.textContent = question.helperText;
    wrapper.appendChild(helper);
  }

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
      if (typeof question.showIf === 'function' && !question.showIf(formData)) {
        return;
      }
      branchContainer.appendChild(renderField(question));
    });
  });
}

function getFieldValue(field) {
  if (field.multiple) {
    return Array.from(field.selectedOptions).map((opt) => opt.value);
  }
  return field.value;
}

function getFormData() {
  const data = {};
  const fields = form.querySelectorAll('input, select, textarea');

  fields.forEach((field) => {
    data[field.name] = getFieldValue(field);
  });

  return data;
}

function validateForm(formData) {
  const visibleQuestions = window.getVisibleQuestions(formData);
  const missingLabels = [];

  visibleQuestions.forEach((question) => {
    if (!question.required) {
      return;
    }

    const value = formData[question.key];
    if (Array.isArray(value)) {
      if (value.length === 0) {
        missingLabels.push(question.label);
      }
      return;
    }

    if (value === undefined || value === null || String(value).trim() === '') {
      missingLabels.push(question.label);
    }
  });

  return missingLabels;
}

function showValidationErrors(missingLabels) {
  if (missingLabels.length === 0) {
    validationContainer.hidden = true;
    validationContainer.textContent = '';
    return;
  }

  validationContainer.hidden = false;
  validationContainer.textContent = `Uzupełnij wymagane pola: ${missingLabels.join(', ')}.`;
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
  const formData = getFormData();
  renderBranchQuestions(formData);
  showValidationErrors([]);
});

form.addEventListener('submit', (event) => {
  event.preventDefault();
  const data = getFormData();
  const missingLabels = validateForm(data);

  if (missingLabels.length > 0) {
    showValidationErrors(missingLabels);
    return;
  }

  showValidationErrors([]);
  const result = window.evaluateCase(data);
  showResult(result);
});

renderBaseQuestions();
renderBranchQuestions(getFormData());
