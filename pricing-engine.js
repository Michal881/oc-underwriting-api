/*
  MVP pricing engine v1.
  Stawki i mnożniki są placeholderami i będą skalibrowane
  na podstawie docelowej taryfy źródłowej w kolejnych iteracjach.
*/

const BASE_RATES_BY_INDUSTRY = {
  production: 0.002,
  trade: 0.0015,
  construction: 0.006,
  physical_services: 0.004,
  business_services: 0.001,
  hospitality_public: 0.003,
  energy_infrastructure: 0.005
};

const MIN_PREMIUM_BY_INDUSTRY = {
  default: 1500,
  construction: 3000,
  energy_infrastructure: 5000
};

function toNumber(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : 0;
}

function resolvePricingIndustryGroup(formData) {
  if (formData.dzialalnosc === 'produkcja') return 'production';
  if (formData.dzialalnosc === 'handel') return 'trade';
  if (formData.dzialalnosc === 'budownictwo') return 'construction';
  if (formData.dzialalnosc === 'gastronomia_hotelarstwo') return 'hospitality_public';
  if (formData.dzialalnosc === 'transport') return 'physical_services';
  if (formData.dzialalnosc === 'uslugi') return 'business_services';
  return 'business_services';
}

function calculateBaseExposure(formData, pricingIndustryGroup) {
  const turnover = toNumber(formData.obrot);

  if (pricingIndustryGroup === 'construction') {
    return toNumber(formData.wartosc_projektow) > 0 ? toNumber(formData.wartosc_projektow) : turnover;
  }

  if (pricingIndustryGroup === 'physical_services') {
    return toNumber(formData.liczba_pracownikow) * 50000;
  }

  if (pricingIndustryGroup === 'hospitality_public') {
    const visitorsExposure = toNumber(formData.liczba_klientow) * 12 * 20;
    return Math.max(visitorsExposure, turnover);
  }

  return turnover;
}

function calculateIndicativePremium(formData, uwResult) {
  const pricingIndustryGroup = resolvePricingIndustryGroup(formData);
  const baseRate = BASE_RATES_BY_INDUSTRY[pricingIndustryGroup] || BASE_RATES_BY_INDUSTRY.business_services;
  const baseExposure = calculateBaseExposure(formData, pricingIndustryGroup);
  const appliedMultipliers = [];

  let multiplier = 1;
  let referralByPricing = false;

  const applyMultiplier = (code, label, factor, triggersReferral = false) => {
    multiplier *= factor;
    appliedMultipliers.push({ code, label, factor });
    if (triggersReferral) {
      referralByPricing = true;
    }
  };

  if (formData.produkt === 'tak') {
    applyMultiplier('product_exposure', 'Ekspozycja produktowa', 1.2);
  }

  if (formData.usa_kanada === 'tak') {
    applyMultiplier('usa_canada', 'Ekspozycja USA/Kanada', 2, true);
  }

  if (formData.srodowisko === 'średnie') {
    applyMultiplier('env_medium', 'Ekspozycja środowiskowa: średnia', 1.25);
  }

  if (formData.srodowisko === 'duże') {
    applyMultiplier('env_large', 'Ekspozycja środowiskowa: duża', 1.5, true);
  }

  if (formData.podwykonawcy === 'tak') {
    applyMultiplier('subcontractors', 'Podwykonawcy', 1.15);
  }

  if (formData.prace_na_wysokosci === 'tak') {
    applyMultiplier('height_work', 'Prace na wysokości', 1.15);
  }

  if (formData.roboty_ziemne === 'tak') {
    applyMultiplier('excavation', 'Roboty ziemne / wykopy', 1.1);
  }

  if (toNumber(formData.szkody_historyczne) > 2) {
    applyMultiplier('multiple_or_large_claims', 'Szkodowość: multiple/large claims', 1.5, true);
  }

  const technicalPremium = baseExposure * baseRate * multiplier;

  const minimumPremium = MIN_PREMIUM_BY_INDUSTRY[pricingIndustryGroup]
    || MIN_PREMIUM_BY_INDUSTRY.default;

  const estimatedPremium = Math.max(technicalPremium, minimumPremium);

  return {
    pricing_industry_group: pricingIndustryGroup,
    base_exposure: baseExposure,
    base_rate: baseRate,
    applied_multipliers: appliedMultipliers,
    total_multiplier: multiplier,
    technical_premium: technicalPremium,
    minimum_premium: minimumPremium,
    estimated_premium: estimatedPremium,
    refer_to_underwriter: Boolean(uwResult?.refer_to_underwriter) || referralByPricing,
    note: 'Wynik orientacyjny MVP — nie jest ofertą ubezpieczenia.'
  };
}

window.PRICING_ENGINE = {
  calculateIndicativePremium
};
