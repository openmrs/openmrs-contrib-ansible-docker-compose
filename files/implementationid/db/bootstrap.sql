/*
MySQL Data Transfer
Source Host: localhost
Source Database: implmentationid
Target Host: localhost
Target Database: implementationid
Date: 7/11/2007 3:52:38 PM
*/

SET FOREIGN_KEY_CHECKS=0;
-- ----------------------------
-- Table structure for access_log
-- ----------------------------
DROP TABLE IF EXISTS `access_log`;
CREATE TABLE `access_log` (
  `access_log_id` int(11) NOT NULL auto_increment,
  `ip_address` varchar(255) NOT NULL,
  `access_date` date NOT NULL default '0000-00-00',
  `access_time` time NOT NULL,
  `implementation_id` char(20) NOT NULL,
  `success` int(1) NOT NULL default '0',
  PRIMARY KEY  (`access_log_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ----------------------------
-- Table structure for implementation_id
-- ----------------------------
DROP TABLE IF EXISTS `implementation_id`;
CREATE TABLE `implementation_id` (
  `implementation_id` char(20) NOT NULL,
  `passphrase` varchar(255) NOT NULL,
  `description` varchar(255) NOT NULL,
  PRIMARY KEY  (`implementation_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
