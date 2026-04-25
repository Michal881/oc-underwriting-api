/*
  Engine pytań i oceny case'u dla MVP.
  Plik zawiera:
  - definicje pytań bazowych i branchowych,
  - prostą klasyfikację branż,
  - evaluateCase() zwracające wynik underwritingowy.
*/

const QUESTION_ENGINE = {
  industries: [
    { value: 'produkcja', label: 'Produkcja' },
    { value: 'handel', label: 'Handel' },
    { value: 'uslugi', label: 'Usługi' },
    { value: 'budownictwo', label: 'Budownictwo' },
    { value: 'gastronomia_hotelarstwo', label: 'Gastronomia / Hotelarstwo' },
    { value: 'transport', label: 'Transport' },
    // Wyłączone przez zakres zadania:
    { value: 'rolnictwo', label: 'Rolnictwo (poza zakresem)', excluded: true },
    { value: 'oc_zawodowe', label: 'OC zawodowe (poza zakresem)', excluded: true },
    { value: 'zawody_techniczne', label: 'Zawody techniczne (poza zakresem)', excluded: true }
  ],

  baseQuestions: [
    { key: 'dzialalnosc', label: 'działalność', type: 'select', required: true },
    { key: 'opis_dzialalnosci', label: 'opis działalności', type: 'text', required: true },
    { key: 'obrot', label: 'obrót', type: 'number', required: true },
    { key: 'liczba_pracownikow', label: 'liczba pracowników', type: 'number', required: true },
    { key: 'produkt', label: 'produkt (tak/nie)', type: 'yesno', required: true },
    { key: 'praca_u_klienta', label: 'praca u klienta', type: 'yesno', required: true },
    { key: 'mienie_klienta', label: 'mienie klienta (CCC)', type: 'yesno', required: true },
    { key: 'srodowisko', label: 'środowisko', type: 'select', options: ['brak', 'małe', 'średnie', 'duże'], required: true },
    { key: 'usa_kanada', label: 'USA/Kanada', type: 'yesno', required: true },
    { key: 'szkody_historyczne', label: 'szkody historyczne', type: 'number', required: true }
  ],

  branchQuestions: {
    construction: [
      { key: 'typ_prac', label: 'typ prac', type: 'text', required: true },
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
      }
    ],
    environmental: [
      {
        key: 'substancje',
        label: 'substancje',
        type: 'multiselect',
        options: [
          'brak',
          'paliwa / oleje',
          'chemikalia',
          'farby / lakiery / rozpuszczalniki',
          'odpady',
          'ścieki technologiczne',
          'gazy techniczne',
          'pyły / emisje',
          'inne'
        ],
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

  if (formData.srodowisko !== 'brak' && formData.srodowisko !== '') {
    branches.push('environmental');
  }

  return branches;
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
  const industry_group = classifyIndustry(formData);
  const risk_flags = [];
  const coverages = ['OC działalności'];
  let selected_model = 'M1';

  // OC produktu + rozszerzenia
  if (formData.produkt === 'tak') {
    coverages.push('OC produktu');
    selected_model = 'M2';

    if (formData.usa_kanada === 'tak') {
      coverages.push('rozszerzone OC produktu');
      selected_model = 'M3';
      risk_flags.push('Ekspozycja USA/Kanada');
    }
  }

  // Ekspozycja środowiskowa
  if (formData.srodowisko !== 'brak') {
    coverages.push('OC środowiskowe (cywilne)');
    selected_model = selected_model === 'M3' ? 'M5' : 'M4';

    if (formData.srodowisko === 'duże') {
      coverages.push('szkody ekologiczne (public law)');
      risk_flags.push('Duża ekspozycja środowiskowa');
      selected_model = 'M6';
    }
  }

  // Flagi ryzyka z pytań ogólnych
  if (Number(formData.szkody_historyczne || 0) > 2) {
    risk_flags.push('Podwyższona szkodowość historyczna');
  }

  if (formData.praca_u_klienta === 'tak') {
    risk_flags.push('Prace wykonywane u klienta');
  }

  if (formData.mienie_klienta === 'tak') {
    risk_flags.push('Mienie klienta w pieczy (CCC)');
  }

  // Branch logic
  if (formData.dzialalnosc === 'budownictwo') {
    risk_flags.push('Ryzyko budowlane');
    if (formData.podwykonawcy === 'tak') {
      risk_flags.push('Udział podwykonawców');
    }
    if (formData.roboty_ziemne === 'tak') {
      risk_flags.push('Roboty ziemne / wykopy');
    }
    if (formData.prace_na_wysokosci === 'tak') {
      risk_flags.push('Prace na wysokości');
    }
  }

  if (formData.dzialalnosc === 'gastronomia_hotelarstwo' && Number(formData.liczba_klientow || 0) > 5000) {
    risk_flags.push('Wysoka ekspozycja publiczna');
  }

  const selectedSubstances = Array.isArray(formData.substancje) ? formData.substancje : [];
  if (selectedSubstances.length > 0 && !selectedSubstances.includes('brak')) {
    risk_flags.push('Obecność substancji potencjalnie szkodliwych');
  }

  const refer_to_underwriter =
    risk_flags.length >= 3 ||
    formData.usa_kanada === 'tak' ||
    formData.srodowisko === 'duże';

  return {
    industry_group,
    selected_model,
    risk_flags,
    coverages,
    refer_to_underwriter
  };
}

// Udostępnienie engine globalnie dla app.js
window.QUESTION_ENGINE = QUESTION_ENGINE;
window.getActiveBranches = getActiveBranches;
window.getVisibleQuestions = getVisibleQuestions;
window.evaluateCase = evaluateCase;
