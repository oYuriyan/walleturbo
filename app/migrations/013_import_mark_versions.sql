-- Revisões das origens preservam vínculos e impedem reenvios após desfazimento.
ALTER TABLE import_marks ADD COLUMN version integer NOT NULL DEFAULT 0;
UPDATE import_marks SET version = 1 WHERE resource_id IS NOT NULL;
