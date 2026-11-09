-- Schema-Version 4: Der erste Prompt einer Session gilt als ihr Auftrag (Anzeige im Cockpit).
-- Er wird gekürzt gespeichert und gehört wie die ganze Datenbank nur dem lokalen Benutzer.

ALTER TABLE session ADD COLUMN first_prompt TEXT;
