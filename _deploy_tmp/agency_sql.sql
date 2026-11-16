-- Flovo Content Agency — DB migration (v1)
-- Independent per-bot conversations + messages for the 6-bot content team.
-- Run against the `flovo` database (same DB ai_gateway.php already uses).

CREATE TABLE IF NOT EXISTS flovo_agency_conversations (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id INT UNSIGNED NOT NULL,
  bot_id VARCHAR(40) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uniq_user_bot (user_id, bot_id),
  KEY idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS flovo_agency_messages (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  conversation_id INT UNSIGNED NOT NULL,
  role VARCHAR(16) NOT NULL,            -- 'user' | 'assistant' | 'subbot'
  sub_bot_id VARCHAR(40) DEFAULT NULL,  -- set only when role='subbot' (which sub-bot produced this)
  content MEDIUMTEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_conv (conversation_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
