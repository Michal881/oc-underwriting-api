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
    { key: 'dzialalnosc', label: 'działalność', type: 'select' },
    { key: 'opis_dzialalnosci', label: 'opis działalności', type: 'text' },
    { key: 'obrot', label: 'obrót', type: 'number' },
    { key: 'liczba_pracownikow', label: 'liczba pracowników', type: 'number' },
    { key: 'produkt', label: 'produkt (tak/nie)', type: 'yesno' },
    { key: 'praca_u_klienta', label: 'praca u klienta', type: 'yesno' },
    { key: 'mienie_klienta', label: 'mienie klienta (CCC)', type: 'yesno' },
    { key: 'srodowisko', label: 'środowisko', type: 'select', options: ['brak', 'małe', 'średnie', 'duże'] },
    { key: 'usa_kanada', label: 'USA/Kanada', type: 'yesno' },
    { key: 'szkody_historyczne', label: 'szkody historyczne', type: 'number' }
  ],

  branchQuestions: {
    construction: [
      { key: 'typ_prac', label: 'typ prac', type: 'text' },
      { key: 'podwykonawcy', label: 'podwykonawcy', type: 'yesno' },
      { key: 'wartosc_projektow', label: 'wartość projektów', type: 'number' }
    ],
    hospitality: [
      { key: 'liczba_klientow', label: 'liczba klientów', type: 'number' }
    ],
    environmental: [
      { key: 'substancje', label: 'substancje', type: 'text' },
      { key: 'pojemnosc', label: 'pojemność', type: 'number' }
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

  if (formData.srodowisko !== 'brak') {
    branches.push('environmental');
  }

  return branches;
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
  }

  if (formData.dzialalnosc === 'gastronomia_hotelarstwo' && Number(formData.liczba_klientow || 0) > 5000) {
    risk_flags.push('Wysoka ekspozycja publiczna');
  }

  if (formData.substancje && formData.substancje.trim().length > 0) {
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
window.evaluateCase = evaluateCase;
