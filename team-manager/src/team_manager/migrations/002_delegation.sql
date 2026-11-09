-- Schema-Version 2: Delegation. Ein Manager-Agent (Profil: can_delegate: true) beauftragt andere Teammitglieder.
-- Der Unterauftrag verweist auf den Auftrag des Managers.

ALTER TABLE agent ADD COLUMN can_delegate INTEGER NOT NULL DEFAULT 0 CHECK (can_delegate IN (0, 1));

ALTER TABLE task ADD COLUMN parent_task_id INTEGER REFERENCES task (id);

CREATE INDEX task_parent ON task (parent_task_id) WHERE parent_task_id IS NOT NULL;
