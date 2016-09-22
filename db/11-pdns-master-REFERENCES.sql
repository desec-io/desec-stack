USE pdnsmaster;

-- As recommended by https://doc.powerdns.com/md/authoritative/backend-generic-mysql/
ALTER TABLE `records` ADD CONSTRAINT `records_ibfk_1` FOREIGN KEY (`domain_id`) REFERENCES `domains` (`id`) ON DELETE CASCADE;
ALTER TABLE `domainmetadata` ADD CONSTRAINT `domainmetadata_ibfk_1` FOREIGN KEY (`domain_id`) REFERENCES `domains` (`id`) ON DELETE CASCADE;
