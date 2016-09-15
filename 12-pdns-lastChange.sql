USE pdns;

-- For use with zone-lastchange-query (see https://doc.powerdns.com/md/authoritative/backend-generic-sql/#masterslave-queries)
ALTER TABLE domains ADD COLUMN `change_date` int(10) UNSIGNED NOT NULL;

CREATE PROCEDURE updateChangeDate(IN _id INT)
MODIFIES SQL DATA
UPDATE domains SET change_date=UNIX_TIMESTAMP() WHERE id = _id;

DELIMITER $$

CREATE TRIGGER insert_trig
AFTER INSERT ON records FOR EACH ROW
IF NEW.disabled != 1 THEN
	CALL updateChangeDate(NEW.domain_id);
END IF;
$$

CREATE TRIGGER delete_trig
AFTER DELETE ON records FOR EACH ROW
IF OLD.disabled != 1 THEN
	CALL updateChangeDate(OLD.domain_id);
END IF;
$$

CREATE TRIGGER update_trig
AFTER UPDATE ON records FOR EACH ROW
IF OLD.disabled != 1 OR NEW.disabled != 1 THEN
	CALL updateChangeDate(OLD.domain_id);
END IF;
$$

DELIMITER ;

