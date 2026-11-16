export const CURRENCIES = {
  USD: { code: "USD", symbol: "$", name: "US Dollar", rate: 1.0 },
  EUR: { code: "EUR", symbol: "€", name: "Euro", rate: 0.93 },
  GBP: { code: "GBP", symbol: "£", name: "British Pound", rate: 0.79 },
  INR: { code: "INR", symbol: "₹", name: "Indian Rupee", rate: 83.2 },
  AUD: { code: "AUD", symbol: "A$", name: "Australian Dollar", rate: 1.52 },
  CAD: { code: "CAD", symbol: "C$", name: "Canadian Dollar", rate: 1.35 },
  SGD: { code: "SGD", symbol: "S$", name: "Singapore Dollar", rate: 1.34 },
  JPY: { code: "JPY", symbol: "¥", name: "Japanese Yen", rate: 151.3 },
  CNY: { code: "CNY", symbol: "¥", name: "Chinese Yuan", rate: 7.23 },
  CHF: { code: "CHF", symbol: "CHF", name: "Swiss Franc", rate: 0.90 },
  HKD: { code: "HKD", symbol: "HK$", name: "Hong Kong Dollar", rate: 7.82 },
  NZD: { code: "NZD", symbol: "NZ$", name: "New Zealand Dollar", rate: 1.66 },
  SEK: { code: "SEK", symbol: "kr", name: "Swedish Krona", rate: 10.51 },
  KRW: { code: "KRW", symbol: "₩", name: "South Korean Won", rate: 1350.0 },
  BRL: { code: "BRL", symbol: "R$", name: "Brazilian Real", rate: 5.05 },
  MXN: { code: "MXN", symbol: "$", name: "Mexican Peso", rate: 16.5 },
  ZAR: { code: "ZAR", symbol: "R", name: "South African Rand", rate: 18.9 },
  RUB: { code: "RUB", symbol: "₽", name: "Russian Ruble", rate: 92.5 },
  AED: { code: "AED", symbol: "د.إ", name: "UAE Dirham", rate: 3.67 },
  SAR: { code: "SAR", symbol: "﷼", name: "Saudi Riyal", rate: 3.75 },
  TRY: { code: "TRY", symbol: "₺", name: "Turkish Lira", rate: 32.1 },
  PLN: { code: "PLN", symbol: "zł", name: "Polish Zloty", rate: 3.98 },
  THB: { code: "THB", symbol: "฿", name: "Thai Baht", rate: 36.4 },
  IDR: { code: "IDR", symbol: "Rp", name: "Indonesian Rupiah", rate: 15900.0 },
  MYR: { code: "MYR", symbol: "RM", name: "Malaysian Ringgit", rate: 4.74 },
  PHP: { code: "PHP", symbol: "₱", name: "Philippine Peso", rate: 56.4 },
  VND: { code: "VND", symbol: "₫", name: "Vietnamese Dong", rate: 24950.0 },
  ILS: { code: "ILS", symbol: "₪", name: "Israeli Shekel", rate: 3.68 },
  DKK: { code: "DKK", symbol: "kr", name: "Danish Krone", rate: 6.94 },
  NOK: { code: "NOK", symbol: "kr", name: "Norwegian Krone", rate: 10.85 }
};

export function formatCurrency(amount, currencyCode = "USD") {
  const num = Number(amount) || 0;
  const currency = CURRENCIES[currencyCode] || CURRENCIES.USD;
  const converted = num * currency.rate;
  
  // Format with standard locale string for commas, and prefix with symbol
  return `${currency.symbol}${converted.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })}`;
}
