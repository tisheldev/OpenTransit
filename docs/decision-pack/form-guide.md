# Ministry SIRI application: completion guide

Source: [official one-page form supplied by the developer](https://www.gov.il/BlobFolder/generalpage/real_time_information_siri/he/real_time_information_receipt_form.pdf), visually inspected and downloaded on 5 September 2026. The original has no interactive form fields. It directs applicants to `ptsupport@mot.gov.il`.

The prepared PDF preserves the official page and terms. Only the four-line project-purpose statement has been prefilled; email, phone, mobile, IP and identity-number boxes have been made fillable. Hebrew name, corporation details and signature remain blank on their original lines; write them after printing or use your PDF viewer's Hebrew-capable text tool. No identity, IP, signature or legal acceptance has been supplied.

## Exact fields

| Official field | What you enter |
| --- | --- |
| שם ומשפחה של המבקש בעברית | Your full name in Hebrew |
| שם התאגיד | Actual corporation/entity name, if applicable; if applying personally, ask MOT what to enter |
| מספר התאגיד | Actual registration number, if applicable; do not substitute an identity number without MOT instructions |
| מייל | The address where you want MOT to contact you |
| טלפון | Contact telephone; the form does not state whether duplication with mobile or omission is accepted |
| טלפון נייד | Mobile number |
| מספר IP סטטי | Static **public outgoing IPv4** of the future ingester; do not enter a local `192.168.*`/`10.*` address or assume today's public IP is static |
| מהות הדרישה | The project-purpose draft below, already placed in the prepared PDF |
| ת״ז | Your identity number; enter directly in your private completed copy |
| חתימה | Your signature, after reviewing the Ministry terms |

The form explicitly tells the applicant to approach their communications provider for a static IP. It does not specify accepted geography, multiple IP support or IP-change procedure; the emails ask those questions. No hosting provider or paid plan has been selected.

## Purpose statement placed on the form

פיתוח שירות בקוד פתוח לתכנון נסיעות בתחבורה הציבורית בישראל.

הצגת תחזיות הגעה, עיכובים ומיקומי כלי רכב, ושילובם בלוחות הזמנים.

השירות מיועד לשימוש הציבור ללא פרסומות וללא תשלום בשלב המתוכנן.

הגישה למקור המידע תתבצע בשרת מרכזי, בהתאם להרשאות ולמגבלות שייקבעו.

This describes the intended product rather than claiming it is already deployed. Change it before signing if it does not match your intended use. The companion email identifies the project as OpenTransit Israel and requests separate alert access and clarification on sharing/retention.

## Terms: what is visible and what is still unanswered

The form says that signing accepts a disclaimer of Ministry liability for losses or expenses arising from use or publication of the information, including errors, omissions or failure to update it. Read the original Hebrew wording before signing.

The one-page form does not expressly settle the project's separate questions about API redistribution, public fixture samples, historical retention or alert-feed terms. A signature on this form is not evidence that those questions, or the static GTFS dataset terms, have been resolved. They are included in the email for a written answer.

## Before sending

- Replace every bracketed placeholder in the chosen email and remove instructions/unused alternative paragraphs.
- Check the entered identity/contact/IP details and the project-purpose wording.
- Read the Ministry terms and sign only if you choose to accept them.
- Save a private completed/signed copy. Attach that copy for email A; email B is the preliminary question and does not claim to attach a completed form.
- Send to `ptsupport@mot.gov.il`, then record the actual send date and any ticket number in your private notes.
