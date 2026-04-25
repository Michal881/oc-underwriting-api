/*
  Engine pytań i oceny case'u dla MVP.
  Plik zawiera:
  - definicje pytań bazowych i branchowych,
  - prostą klasyfikację branż,
  - evaluateCase() zwracające wynik underwritingowy.
*/

const QUESTION_ENGINE = {
  industries: window.REFERENCE_DATA.industryGroups,

  baseQuestions: [
    { key: 'dzialalnosc', label: 'działalność', type: 'select', required: true },
    { key: 'opis_dzialalnosci', label: 'opis działalności', type: 'text', required: true },
    { key: 'obrot', label: 'obrót', type: 'number', required: true },
    { key: 'liczba_pracownikow', label: 'liczba pracowników', type: 'number', required: true },
    { key: 'produkt', label: 'produkt (tak/nie)', type: 'yesno', required: true },
    { key: 'praca_u_klienta', label: 'praca u klienta', type: 'yesno', required: true },
    { key: 'mienie_klienta', label: 'mienie klienta (CCC)', type: 'yesno', required: true },
    { key: 'srodowisko', label: 'środowisko', type: 'select', options: window.REFERENCE_DATA.environmentalExposureLevels, required: true },
    { key: 'usa_kanada', label: 'USA/Kanada', type: 'yesno', required: true },
    { key: 'szkody_historyczne', label: 'szkody historyczne', type: 'number', required: true }
  ],

  branchQuestions: {
    construction: [
      { key: 'typ_prac', label: 'typ prac', type: 'select', options: window.REFERENCE_DATA.constructionWorkTypes, required: true },
      { key: 'podwykonawcy', label: 'podwykonawcy', type: 'yesno', required: true },
      { key: 'wartosc_projektow', label: 'wartość projektów', type: 'number', required: true },
      { key: 'roboty_ziemne', label: 'czy prace obejmują roboty ziemne / wykopy?', type: 'yesno', required: true },
      { key: 'prace_na_wysokosci', label: 'czy prace obejmują prace na wysokości?', type: 'yesno', required: true }
    ],
    hospitality: [
      {
        key: 'liczba_klientow',
        label: 'liczba klientów / gości / uczestników miesięcznie',
        type: 'number',
        helperText: 'Podaj przybliżoną średnią miesięczną.',
        required: true
      },
      {
        key: 'ekspozycja_eventowa',
        label: 'czy działalność obejmuje organizację eventów / imprez?',
        type: 'yesno',
        required: true
      }
    ],
    environmental: [
      {
        key: 'substancje',
        label: 'substancje',
        type: 'multiselect',
        options: window.REFERENCE_DATA.environmentalSubstances,
        required: true
      },
      {
        key: 'substancje_inne_opis',
        label: 'opisz substancję / instalację',
        type: 'text',
        required: true,
        showIf: (formData) => {
          const selected = Array.isArray(formData.substancje) ? formData.substancje : [];
          return selected.includes('inne');
        }
      },
      {
        key: 'pojemnosc',
        label: 'łączna pojemność / ilość magazynowanych substancji',
        type: 'number',
        helperText: 'Dla MVP wystarczy wartość przybliżona.',
        unitHint: 'litry lub kg',
        required: true
      }
    ]
  }
};

function classifyIndustry(formData) {
  if (formData.dzialalnosc === 'budownictwo') {
    return 'budownictwo';
  }

  if (formData.dzialalnosc === 'gastronomia_hotelarstwo') {
    return 'hospitality/public exposure';
  }

  if (formData.srodowisko === 'średnie' || formData.srodowisko === 'duże') {
    return 'environmental';
  }

  return 'general';
}

function getActiveBranches(formData) {
  const branches = [];

  if (formData.dzialalnosc === 'budownictwo') {
    branches.push('construction');
  }

  if (formData.dzialalnosc === 'gastronomia_hotelarstwo') {
    branches.push('hospitality');
  }

  if (formData.srodowisko === 'średnie' || formData.srodowisko === 'duże') {
    branches.push('environmental');
  }

  return branches;
}

function sanitizeFormData(formData) {
  const safeData = {};

  QUESTION_ENGINE.baseQuestions.forEach((question) => {
    if (Object.prototype.hasOwnProperty.call(formData, question.key)) {
      safeData[question.key] = formData[question.key];
    }
  });

  const activeBranches = getActiveBranches(safeData);
  activeBranches.forEach((branch) => {
    const questions = QUESTION_ENGINE.branchQuestions[branch] || [];
    questions.forEach((question) => {
      if (typeof question.showIf === 'function' && !question.showIf(safeData)) {
        return;
      }

      if (Object.prototype.hasOwnProperty.call(formData, question.key)) {
        safeData[question.key] = formData[question.key];
      }
    });
  });

  return safeData;
}

function getVisibleQuestions(formData) {
  const visible = [...QUESTION_ENGINE.baseQuestions];
  const branches = getActiveBranches(formData);

  branches.forEach((branch) => {
    const questions = QUESTION_ENGINE.branchQuestions[branch] || [];
    questions.forEach((question) => {
      if (typeof question.showIf === 'function' && !question.showIf(formData)) {
        return;
      }
      visible.push(question);
    });
  });

  return visible;
}

function evaluateCase(formData) {
  const sanitizedData = sanitizeFormData(formData);
  const industry_group = classifyIndustry(sanitizedData);
  const risk_flags = [];
  const coverages = [window.REFERENCE_DATA.coverageLabels.businessLiability];
  let selected_model = window.REFERENCE_DATA.pricingModelLabels.M1;

  // OC produktu + rozszerzenia
  if (sanitizedData.produkt === 'tak') {
    coverages.push(window.REFERENCE_DATA.coverageLabels.productLiability);
    selected_model = window.REFERENCE_DATA.pricingModelLabels.M2;

    if (sanitizedData.usa_kanada === 'tak') {
      coverages.push(window.REFERENCE_DATA.coverageLabels.extendedProductLiability);
      selected_model = window.REFERENCE_DATA.pricingModelLabels.M3;
      risk_flags.push(window.REFERENCE_DATA.riskFlagLabels.usaCanadaExposure);
    }
  }

  // Ekspozycja środowiskowa
  if (sanitizedData.srodowisko !== 'brak') {
    coverages.push(window.REFERENCE_DATA.coverageLabels.environmentalCivilLiability);
    selected_model = selected_model === window.REFERENCE_DATA.pricingModelLabels.M3
      ? window.REFERENCE_DATA.pricingModelLabels.M5
      : window.REFERENCE_DATA.pricingModelLabels.M4;

    if (sanitizedData.srodowisko === 'duże') {
      coverages.push(window.REFERENCE_DATA.coverageLabels.environmentalPublicLaw);
      risk_flags.push(window.REFERENCE_DATA.riskFlagLabels.highEnvironmentalExposure);
      selected_model = window.REFERENCE_DATA.pricingModelLabels.M6;
    }
  }

  // Flagi ryzyka z pytań ogólnych
  if (Number(sanitizedData.szkody_historyczne || 0) > 2) {
    risk_flags.push(window.REFERENCE_DATA.riskFlagLabels.elevatedClaimsHistory);
  }

  if (sanitizedData.praca_u_klienta === 'tak') {
    risk_flags.push(window.REFERENCE_DATA.riskFlagLabels.workAtClientSite);
  }

  if (sanitizedData.mienie_klienta === 'tak') {
    risk_flags.push(window.REFERENCE_DATA.riskFlagLabels.customerPropertyInCare);
  }

  // Branch logic
  if (sanitizedData.dzialalnosc === 'budownictwo') {
    risk_flags.push(window.REFERENCE_DATA.riskFlagLabels.constructionRisk);
    if (sanitizedData.podwykonawcy === 'tak') {
      risk_flags.push(window.REFERENCE_DATA.riskFlagLabels.subcontractorInvolvement);
    }
    if (sanitizedData.roboty_ziemne === 'tak') {
      risk_flags.push(window.REFERENCE_DATA.riskFlagLabels.earthworks);
    }
    if (sanitizedData.prace_na_wysokosci === 'tak') {
      risk_flags.push(window.REFERENCE_DATA.riskFlagLabels.workingAtHeight);
    }
  }

  if (sanitizedData.dzialalnosc === 'gastronomia_hotelarstwo' && Number(sanitizedData.liczba_klientow || 0) > 5000) {
    risk_flags.push(window.REFERENCE_DATA.riskFlagLabels.highPublicExposure);
  }

  const selectedSubstances = Array.isArray(sanitizedData.substancje) ? sanitizedData.substancje : [];
  if (selectedSubstances.length > 0 && !selectedSubstances.includes('brak')) {
    risk_flags.push(window.REFERENCE_DATA.riskFlagLabels.harmfulSubstancesPresent);
  }

  const refer_to_underwriter =
    risk_flags.length >= 3 ||
    sanitizedData.usa_kanada === 'tak' ||
    sanitizedData.srodowisko === 'duże';

  return {
    industry_group,
    selected_model,
    risk_flags,
    coverages,
    refer_to_underwriter,
    form_data: { ...sanitizedData }
  };
}

// Udostępnienie engine globalnie dla app.js
window.QUESTION_ENGINE = QUESTION_ENGINE;
window.getActiveBranches = getActiveBranches;
window.getVisibleQuestions = getVisibleQuestions;
window.sanitizeFormData = sanitizeFormData;
window.evaluateCase = evaluateCase;
