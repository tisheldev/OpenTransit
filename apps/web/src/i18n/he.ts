// Hebrew is the source language. Strings address the passenger with the gender-neutral
// plural imperative (design: Language and layout rules). English mirrors these keys.
// Placeholders are {name}; both dictionaries must use the same ones.

import { he_compare } from "./parts/compare.he";
import { he_map } from "./parts/map.he";
import { he_nav } from "./parts/nav.he";
import { he_secondary } from "./parts/secondary.he";
import { he_shell } from "./parts/shell.he";

// Core strings below; each slice owns its own part file in ./parts (merged at the end).
const core = {
  "app.name": "OpenTransit",
  "app.tagline": "תכנון וניווט בתחבורה ציבורית",
  "app.skipToContent": "דילוג לתוכן",

  "screen.home": "בית",
  "screen.search": "לאן נוסעים?",
  "screen.compare": "השוואת אפשרויות",
  "screen.route": "פרטי מסלול",
  "screen.navigate": "ניווט",
  "screen.stop": "תחנה",
  "screen.trip": "נסיעה",
  "screen.nearby": "תחנות בסביבה",
  "screen.lines": "קווים",
  "screen.settings": "הגדרות",
  "screen.notFound": "הדף לא נמצא",
  "screen.placeholder": "המסך הזה עוד לא נבנה.",
  "screen.backHome": "חזרה לבית",

  "nav.back": "חזרה",
  "nav.locate": "המיקום שלי",

  "settings.language": "שפה",
  "settings.language.he": "עברית",
  "settings.language.en": "English",
  "settings.clearData": "מחיקת כל הנתונים המקומיים",
  "settings.clearData.confirm": "למחוק את המקומות השמורים, החיפושים האחרונים וההגדרות מהמכשיר הזה?",
  "settings.clearData.done": "הנתונים המקומיים נמחקו.",

  "status.checking": "בודקים את מצב הנתונים…",
  "status.ready": "לוח הזמנים זמין",
  "status.coverage": "לוח זמנים מתוכנן מ־{from} עד {until}",
  "status.notReady": "התכנון אינו זמין כרגע",

  "banner.testData": "נתוני בדיקה — לא לוח הזמנים האמיתי",
  "banner.staleData": "לוח הזמנים לא עודכן לאחרונה וייתכן שאינו מעודכן",
  "banner.liveUnavailable": "זמנים בזמן אמת והתראות אינם זמינים",

  "time.scheduled": "מתוכנן",
  "time.now": "עכשיו",
  "time.departAt": "יציאה ב־",
  "time.arriveBy": "הגעה עד",

  "state.loading": "טוענים…",
  "state.retry": "לנסות שוב",
  "state.retryIn": "אפשר לנסות שוב בעוד {seconds} שנ׳",
  "state.empty.noRoute": "לא נמצא מסלול בשעה הזאת. נסו שעה אחרת או נקודה קרובה.",
  "state.empty.noDepartures": "אין יציאות מתוכננות בטווח הזה.",
  "state.empty.noMatches": "לא נמצאו תוצאות. נסו לכתוב אחרת.",
  "state.unavailable.live": "זמנים בזמן אמת והתראות אינם זמינים",
  "state.unavailable.category": "חלק מסוגי התוצאות אינם זמינים כרגע: {categories}",

  "error.outside_window": "השעה שנבחרה מחוץ ללוח הזמנים. אפשר לבחור בין {from} ל־{until}.",
  "error.outside_window.noDates": "השעה שנבחרה מחוץ ללוח הזמנים.",
  "error.invalid_place_ref": "המקום השמור כבר לא מזוהה. מנסים שוב לפי המיקום שלו.",
  "error.invalid_cursor": "הרשימה השתנתה. טוענים אותה מההתחלה.",
  "error.invalid_request": "הבקשה לא התקבלה. נסו שוב.",
  "error.not_found": "לא נמצא עוד בלוח הזמנים.",
  "error.rate_limited": "יותר מדי בקשות. המתינו רגע ונסו שוב.",
  "error.data_expired": "לוח הזמנים דורש עדכון ואינו זמין כרגע.",
  "error.category_unavailable": "החיפוש בסוג הזה אינו זמין כרגע.",
  "error.temporarily_unavailable": "השירות אינו זמין זמנית.",
  "error.network": "אין חיבור ל־OpenTransit. בדקו את החיבור לאינטרנט.",
  "error.unexpected": "משהו השתבש. נסו שוב.",

  "place.stop": "תחנה",
  "place.station": "תחנה מרכזית",
  "place.poi": "מקום",
  "place.address": "כתובת",
} as const;

export const he = { ...core, ...he_map, ...he_shell, ...he_compare, ...he_nav, ...he_secondary } as const;

export type MessageKey = keyof typeof he;
