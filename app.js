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

function setFieldValue(input, question, formData) {
  const existingValue = formData?.[question.key];
  if (existingValue === undefined || existingValue === null) {
    return;
  }

  if (input.multiple) {
    const selectedValues = Array.isArray(existingValue) ? existingValue : [existingValue];
    Array.from(input.options).forEach((option) => {
      option.selected = selectedValues.includes(option.value);
    });
    return;
  }

  if (input.tagName === 'TEXTAREA') {
    input.value = String(existingValue);
    return;
  }

  if (input.type === 'checkbox') {
    input.checked = Boolean(existingValue);
    return;
  }

  input.value = String(existingValue);
}

function renderField(question, formData = {}) {
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
  } else if (question.type === 'checkbox') {
    input = document.createElement('input');
    input.type = 'checkbox';
  } else {
    input = document.createElement('input');
    input.type = 'number';
    input.min = '0';
  }

  input.id = question.key;
  input.name = question.key;
  setFieldValue(input, question, formData);

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
  const formData = getFormData();
  window.QUESTION_ENGINE.baseQuestions.forEach((question) => {
    baseContainer.appendChild(renderField(question, formData));
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
      branchContainer.appendChild(renderField(question, formData));
    });
  });
}

function getFieldValue(field) {
  if (field.type === 'checkbox') {
    return field.checked;
  }
  if (field.multiple) {
    return Array.from(field.selectedOptions).map((opt) => opt.value);
  }
  return field.value;
}

function formatAnswerValue(value) {
  if (Array.isArray(value)) {
    return value.length ? value.join(', ') : '—';
  }
  if (typeof value === 'boolean') {
    return value ? 'tak' : 'nie';
  }
  if (value === undefined || value === null || String(value).trim() === '') {
    return '—';
  }
  return String(value);
}

function renderBranchAnswers(formData) {
  const visibleQuestions = window.getVisibleQuestions(formData);
  const branchQuestionKeys = new Set(
    Object.values(window.QUESTION_ENGINE.branchQuestions)
      .flat()
      .map((question) => question.key)
  );

  const visibleBranchQuestions = visibleQuestions.filter((question) => branchQuestionKeys.has(question.key));
  const target = document.getElementById('out-branch-answers');

  if (!target) {
    return;
  }

  if (visibleBranchQuestions.length === 0) {
    target.textContent = 'Brak';
    return;
  }

  target.textContent = visibleBranchQuestions
    .map((question) => `${question.label}: ${formatAnswerValue(formData[question.key])}`)
    .join(' | ');
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

function formatCurrencyPln(value) {
  return new Intl.NumberFormat('pl-PL', {
    style: 'currency',
    currency: 'PLN',
    maximumFractionDigits: 0
  }).format(Math.round(value));
}

function formatPercent(value) {
  return `${(value * 100).toFixed(2)}%`;
}

function showResult(result, pricingResult) {
  document.getElementById('result').hidden = false;
  document.getElementById('out-industry').textContent = result.industry_group;
  document.getElementById('out-model').textContent = result.selected_model;
  document.getElementById('out-risks').textContent = result.risk_flags.length
    ? result.risk_flags.join(', ')
    : 'Brak';
  document.getElementById('out-coverages').textContent = result.coverages.join(', ');
  document.getElementById('out-referral').textContent = pricingResult.refer_to_underwriter ? 'TAK' : 'NIE';

  document.getElementById('out-estimated-premium').textContent = formatCurrencyPln(pricingResult.estimated_premium);
  document.getElementById('out-base-exposure').textContent = formatCurrencyPln(pricingResult.base_exposure);
  document.getElementById('out-base-rate').textContent = formatPercent(pricingResult.base_rate);

  document.getElementById('out-applied-multipliers').textContent = pricingResult.applied_multipliers.length
    ? pricingResult.applied_multipliers.map((item) => `${item.label} (+${Math.round((item.factor - 1) * 100)}%)`).join(', ')
    : 'Brak';

  document.getElementById('out-minimum-premium').textContent = formatCurrencyPln(pricingResult.minimum_premium);
  document.getElementById('out-pricing-note').textContent = pricingResult.note;
  renderBranchAnswers(result.form_data || {});
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
  const pricingResult = window.PRICING_ENGINE.calculateIndicativePremium(data, result);
  showResult(result, pricingResult);
});

renderBaseQuestions();
renderBranchQuestions(getFormData());
