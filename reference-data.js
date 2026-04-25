/*
  Słowniki referencyjne dla pytań i etykiet underwritingowych.
  Uwaga: brak danych pricingowych (zgodnie z zakresem MVP).
*/

const REFERENCE_DATA = {
  industryGroups: [
    { value: 'produkcja', label: 'Produkcja' },
    { value: 'handel', label: 'Handel' },
    { value: 'uslugi', label: 'Usługi' },
    { value: 'budownictwo', label: 'Budownictwo' },
    { value: 'gastronomia_hotelarstwo', label: 'Gastronomia / Hotelarstwo' },
    { value: 'transport', label: 'Transport' },
    { value: 'rolnictwo', label: 'Rolnictwo (poza zakresem)', excluded: true },
    { value: 'oc_zawodowe', label: 'OC zawodowe (poza zakresem)', excluded: true },
    { value: 'zawody_techniczne', label: 'Zawody techniczne (poza zakresem)', excluded: true }
  ],

  constructionWorkTypes: [
    'roboty ogólnobudowlane',
    'roboty instalacyjne',
    'roboty wykończeniowe',
    'roboty drogowe',
    'roboty ziemne',
    'inne'
  ],

  environmentalSubstances: [
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

  productExposureTypes: [
    'lokalna',
    'krajowa',
    'międzynarodowa (bez USA/Kanady)',
    'USA/Kanada'
  ],

  claimsHistoryOptions: [
    '0',
    '1',
    '2',
    '3+'
  ],

  coverageLabels: {
    businessLiability: 'OC działalności',
    productLiability: 'OC produktu',
    extendedProductLiability: 'rozszerzone OC produktu',
    environmentalCivilLiability: 'OC środowiskowe (cywilne)',
    environmentalPublicLaw: 'szkody ekologiczne (public law)'
  },

  pricingModelLabels: {
    M1: 'M1',
    M2: 'M2',
    M3: 'M3',
    M4: 'M4',
    M5: 'M5',
    M6: 'M6'
  }
};

window.REFERENCE_DATA = REFERENCE_DATA;
