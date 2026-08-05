/*M!999999\- enable the sandbox mode */ 
-- MariaDB dump 10.19  Distrib 10.11.14-MariaDB, for debian-linux-gnu (x86_64)
--
-- Host: localhost    Database: devoteam_dashboard
-- ------------------------------------------------------
-- Server version	10.11.14-MariaDB-0ubuntu0.24.04.1

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Current Database: `devoteam_dashboard`
--

/*!40000 DROP DATABASE IF EXISTS `devoteam_dashboard`*/;

CREATE DATABASE /*!32312 IF NOT EXISTS*/ `devoteam_dashboard` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci */;

USE `devoteam_dashboard`;

--
-- Table structure for table `opportunities`
--

DROP TABLE IF EXISTS `opportunities`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `opportunities` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `country` varchar(100) NOT NULL,
  `created_date` date NOT NULL,
  `deadline` date NOT NULL,
  `deadline_month` varchar(7) NOT NULL,
  `deadline_year` int(11) NOT NULL,
  `days_remaining` int(11) DEFAULT NULL,
  `practice` varchar(100) NOT NULL,
  `description` text DEFAULT NULL,
  `buyer` varchar(255) DEFAULT NULL,
  `opp_type` varchar(50) NOT NULL,
  `status` varchar(100) NOT NULL,
  `budget` double DEFAULT NULL,
  `funding_source` varchar(100) DEFAULT NULL,
  `partner` varchar(100) DEFAULT NULL,
  `financial_offer` double DEFAULT NULL,
  `win_probability` double DEFAULT NULL,
  `weighted_amount` double DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_country` (`country`),
  KEY `idx_practice` (`practice`),
  KEY `idx_status` (`status`),
  KEY `idx_deadline_year` (`deadline_year`),
  KEY `idx_deadline_month` (`deadline_month`),
  KEY `idx_funding_source` (`funding_source`)
) ENGINE=InnoDB AUTO_INCREMENT=361 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `opportunities`
--

LOCK TABLES `opportunities` WRITE;
/*!40000 ALTER TABLE `opportunities` DISABLE KEYS */;
INSERT INTO `opportunities` VALUES
(1,'Bénin','2026-11-07','2026-12-29','2026-12',2026,154,'Digital Transformation','Elaboration de la stratégie de données pour des collectivités locales','ASIN','AMI','Lead',50000,'ENABEL',NULL,49600,NULL,NULL),
(2,'Tunisie','2026-10-11','2026-12-26','2026-12',2026,151,'Risk Advisory','Mise en place d\'une Politique de Sécurité des Systèmes d\'Information (PSSI)','Carrefour - UHD','Prospection','Offre remise',500000,'Fonds Propres','FTHM',445400,0.8,356320),
(3,'Tunisie','2026-06-28','2026-12-23','2026-12',2026,148,'Digital Transformation','élaboration d’un plan de développement du système d’information et de communication 2026-2028','API','Gré à gré','En cours de qualification',50000,'Kfw',NULL,51600,0.2,10320),
(4,'Bénin','2026-07-21','2026-12-20','2026-12',2026,145,'Data Management','Mission de Data Governance et cartographie des données','DGI','AO','Lead',80000,'EU',NULL,68200,NULL,NULL),
(5,'Gabon','2026-08-13','2026-12-17','2026-12',2026,142,'Digital Transformation','Mission AMOA','Petro Gabon','AO','Opportunité détectée',250000,'Fonds Propres','Keyrus',226600,NULL,NULL),
(6,'Mauritanie','2026-08-18','2026-12-13','2026-12',2026,138,'Data Management','Mise en place d\'un tableau de bord de pilotage (Business Intelligence)','WARDIP','DP','Offre gagnée',180000,'AFD',NULL,174300,1,174300),
(7,'Togo','2026-08-11','2026-12-11','2026-12',2026,136,'Risk Advisory','Mise en place d\'une Politique de Sécurité des Systèmes d\'Information (PSSI)','Ministère des Finances du Togo','DP','Lead',750000,'Suisse','Medianet',784700,NULL,NULL),
(8,'Tunisie','2026-09-18','2026-12-10','2026-12',2026,135,'Risk Advisory','Recrutement d\'un cabinet pour l\'audit organisationnel de la DSI','INTT','DP','Offre gagnée',1500000,'BEI','FTHM',1401300,1,1401300),
(9,'Bénin','2026-08-16','2026-12-07','2026-12',2026,132,'Digital Transformation','Urbanisation des architectures des SI sectoriels critiques et mise en place de gouvernance local d\'architecture','ASIN','AO','Offre signée',250000,'AFD',NULL,231700,1,231700),
(10,'Bénin','2026-10-17','2026-12-04','2026-12',2026,129,'Risk Advisory','Elaboration d\'un modèle de référence pour la cyber-résilience et pour la mise en place de Plan de Continuité d\'Activité pour les entreprises opérant des infrastructures d\'information critiques','ASIN','AMI','En cours de préparation',250000,'ENABEL',NULL,250000,0.4,100000),
(11,'Bénin','2026-06-24','2026-12-03','2026-12',2026,128,'Risk Advisory','Recrutement d\'un consultant pour assurer l\'audit des effectifs et des compétences des agents de la Fonction Publique','Projet de Gouvernement Économique et de Délivrance des Services au Bénin (PGEDS)','AMI','Offre perdue',350000,'Banque Mondiale',NULL,317800,NULL,NULL),
(12,'Tunisie','2026-10-03','2026-12-02','2026-12',2026,127,'Data Management','Data Gouv','DIGITECH','AO','Complément d\'information',180000,'Fonds Propres','IMCG',182900,0.2,36580),
(13,'Côte d\'Ivoire','2026-07-04','2026-12-02','2026-12',2026,127,'Risk Advisory','Mise en conformité avec la réglementation sur la protection des données','CDC-CI','DP','Propal shortlistée',250000,'BAD','Expertise Advisors',261600,0.6,156960),
(14,'France','2026-11-06','2026-12-01','2026-12',2026,126,'Risk Advisory','PCA','Orange Bank','AO','Lead',250000,'Fonds Propres',NULL,213500,NULL,NULL),
(15,'Mauritanie','2026-08-27','2026-11-28','2026-11',2026,123,'Digital Transformation','Etude digitalisation services publics Mauritanie','WARDIP','Prospection','Offre signée',50000,'BEI',NULL,44200,1,44200),
(16,'Côte d\'Ivoire','2026-10-07','2026-11-27','2026-11',2026,122,'Risk Advisory','Elaboration du Plan de Continuité d\'Activité (PCA)','GESTOCI','AO','En cours de préparation',1000000,'BAD',NULL,979000,0.4,391600),
(17,'Tunisie','2026-06-13','2026-11-27','2026-11',2026,122,'Risk Advisory','Recrutement d\'un cabinet pour l\'audit organisationnel de la DSI','INTT','AMI','Offre gagnée',1500000,'BEI','FTHM',1340200,1,1340200),
(18,'Cameroun','2026-06-03','2026-11-25','2026-11',2026,120,'Digital Transformation','Etude de cadrage pour la mise en place d\'un ERP','GIMAC','DP','En cours de préparation',180000,'Fonds Propres',NULL,172000,0.4,68800),
(19,'Bénin','2026-08-11','2026-11-24','2026-11',2026,119,'Risk Advisory','Elaboration du Plan de Continuité d\'Activité (PCA)','ANADEC','Prospection','Offre gagnée',350000,'Banque Mondiale','FTHM',356000,1,356000),
(20,'Côte d\'Ivoire','2026-08-21','2026-11-23','2026-11',2026,118,'Digital Transformation','Etude d\'urbanisation du Système d\'Information','CIE Côte d\'Ivoire','AMI','En cours de préparation',350000,'Fonds Propres',NULL,347000,0.4,138800),
(21,'Tunisie','2026-09-22','2026-11-23','2026-11',2026,118,'Digital Transformation','Cost killing','BTK','DP','Hors scope',80000,'Fonds Propres',NULL,82200,NULL,NULL),
(22,'Tunisie','2026-09-03','2026-11-22','2026-11',2026,117,'Digital Transformation','Accompagnement à la Transformation Digitale','Al Baraka','AO','Opportunité détectée',250000,'Fonds Propres',NULL,226100,NULL,NULL),
(23,'Bénin','2026-09-06','2026-11-20','2026-11',2026,115,'Risk Advisory','Recrutement d\'un cabinet pour la mission d\'audit de sécurité du système d\'information de la Direction Générale des Impôts (DGI)','Projet de Gouvernement Économique et de Délivrance des Services au Bénin (PGEDS)','AMI','Non shortlisté',500000,'Kfw',NULL,448800,NULL,NULL),
(24,'Tunisie','2026-06-06','2026-11-18','2026-11',2026,113,'Risk Advisory','Mise en place d\'une Politique de Sécurité des Systèmes d\'Information (PSSI)','Carrefour - UHD','DP','Manifestation remise',120000,'Fonds Propres',NULL,115000,0.4,46000),
(25,'Tunisie','2026-08-07','2026-11-17','2026-11',2026,112,'Data Management','Mission d\'assistance technique pour la gouvernance des données','Poste Tunisienne','AO','Propal shortlistée',350000,'GIZ',NULL,321600,0.6,192960),
(26,'Bénin','2026-10-09','2026-11-15','2026-11',2026,110,'Risk Advisory','Recrutement d\'un cabinet pour la mission d\'audit de sécurité du système d\'information de la Direction Générale des Impôts (DGI)','Projet de Gouvernement Économique et de Délivrance des Services au Bénin (PGEDS)','DP','Manif shortlistée',500000,'Kfw',NULL,445800,0.6,267480),
(27,'Côte d\'Ivoire','2026-06-13','2026-11-15','2026-11',2026,110,'Digital Transformation','Préparation du nouveau SDSI (2026-2030)','CDC-CI','Prospection','Lead',250000,'UNDP','Pragma',238400,NULL,NULL),
(28,'Bénin','2026-08-15','2026-11-15','2026-11',2026,110,'Digital Transformation','Assistance technique pour les études préalables, l’actualisation des sous-projets et l’élaboration des cahiers des charges des outils relatifs à la composante « Renforcement de la gouvernance numérique du secteur public au Congo ».','PATN','DP','En cours de préparation',50000,'Banque Mondiale',NULL,51700,0.4,20680),
(29,'Tunisie','2026-09-23','2026-11-10','2026-11',2026,105,'Data Management','Mission d\'assistance technique pour la gouvernance des données','Banque Tunisienne de Solidarité (BTS)','Consultation','Offre perdue',50000,'ENABEL',NULL,47500,NULL,NULL),
(30,'Tunisie','2026-10-02','2026-11-09','2026-11',2026,104,'Digital Transformation','Testing factory ( Régie ) / Renforcement capacité DSI ( AMOA / PMO )','BTK','AMI','Offre perdue',750000,'Fonds Propres',NULL,693600,NULL,NULL),
(31,'Tunisie','2026-08-28','2026-11-08','2026-11',2026,103,'Risk Advisory','Mise en oeuvre PCA','Office du Commerce Tunisien (OCT)','Avant-vente','Lead',1000000,'Fonds Propres',NULL,961100,NULL,NULL),
(32,'Tunisie','2026-08-08','2026-11-04','2026-11',2026,99,'Data Management','Mission de Data Governance et cartographie des données','Office du Commerce Tunisien (OCT)','DP','Propal shortlistée',1000000,'EU','IMCG',1039900,0.6,623940),
(33,'Bénin','2026-08-04','2026-10-31','2026-10',2026,95,'Digital Transformation','Assistance à Maîtrise d\'Ouvrage (AMOA) pour la refonte du SI','ONEAD','AO','Offre perdue',500000,'Fonds Propres',NULL,468200,NULL,NULL),
(34,'Tunisie','2026-09-06','2026-10-31','2026-10',2026,95,'Digital Transformation','Optimisation des processus','BTK','DP','Complément d\'information',50000,'Fonds Propres',NULL,45000,0.2,9000),
(35,'Côte d\'Ivoire','2026-09-15','2026-10-31','2026-10',2026,95,'Risk Advisory','Mise en conformité avec la réglementation sur la protection des données','CDC-CI','AMI','Non shortlisté',250000,'BAD','Expertise Advisors',219400,NULL,NULL),
(36,'Bénin','2026-07-22','2026-10-28','2026-10',2026,92,'Digital Transformation','Elaboration de l\'outil de gestion prévisionnelle des emplois et compétences (GPEC)','Société des Aéroports du Bénin','Prospection','Offre gagnée',250000,'Kfw',NULL,224400,1,224400),
(37,'Tunisie','2026-06-09','2026-10-28','2026-10',2026,92,'Risk Advisory','Renforcement des capacités en cybersécurité (formation RSSI)','Enda TAO','AMI','Complément d\'information',500000,'Fonds Propres',NULL,485100,0.2,97020),
(38,'Bénin','2026-05-24','2026-10-27','2026-10',2026,91,'Risk Advisory','PSSI','Agence Nationale des Transports Terrestres','Prospection','Lead',350000,'UNDP',NULL,348700,NULL,NULL),
(39,'Tunisie','2026-05-17','2026-10-23','2026-10',2026,87,'Risk Advisory','Mission Gouvernance des Données (prévoir une réunion avec DSI et RSSI (qui est aussi le responsable de la partie Data))','Al Baraka','AMI','Lead',120000,'Fonds Propres','DWT',115100,NULL,NULL),
(40,'Maroc','2026-07-10','2026-10-22','2026-10',2026,86,'Digital Transformation','Appui industrialisation des couches API','BMCI','DP','Propal shortlistée',350000,'Fonds Propres',NULL,343800,0.6,206280),
(41,'Togo','2026-06-29','2026-10-21','2026-10',2026,85,'Risk Advisory','Elaboration du Plan de Continuité d\'Activité (PCA)','Ministère des Finances du Togo','Consultation','Manifestation remise',750000,'Fonds Propres','ADDINN',665000,0.4,266000),
(42,'Bénin','2026-08-13','2026-10-19','2026-10',2026,83,'Risk Advisory','Plan de Continuité de Service (IT)','DGI','DP','Lead',1500000,'AFD',NULL,1573200,NULL,NULL),
(43,'Sénégal','2026-05-20','2026-10-14','2026-10',2026,78,'Digital Transformation','Accompagnement au changement pour le déploiement d\'un nouvel ERP','BCEAO','AMI','En cours de préparation',500000,'UNDP',NULL,489400,0.4,195760),
(44,'Burkina Faso','2026-06-04','2026-10-09','2026-10',2026,73,'Risk Advisory','MAJ du PCA','Instittut National de la Statistique et de la Démographie','Gré à gré','Offre remise',350000,'BAD',NULL,365300,0.8,292240),
(45,'Bénin','2026-07-30','2026-10-05','2026-10',2026,69,'Digital Transformation','Formulation du schéma directeur de la transformation digitale de tout le secteur de l\'EFTP','ASIN','Consultation','Manif shortlistée',750000,'AFD',NULL,686100,0.6,411660),
(46,'Tunisie','2026-06-05','2026-10-04','2026-10',2026,68,'Risk Advisory','Accompagnement pour le Maintien du Système Management de Sécurité de l’Information (SMSI)','Office des Œuvres Universitaires pour le Centre (OOUC)','AO','Opportunité détectée',1500000,'GIZ','IMCG',1334800,NULL,NULL),
(47,'Tunisie','2026-05-30','2026-09-29','2026-09',2026,63,'Digital Transformation','Accompagnement au changement pour le déploiement d\'un nouvel ERP','Office du Commerce Tunisien (OCT)','AO','En cours de qualification',80000,'Fonds Propres','ADDINN',82600,0.2,16520),
(48,'Mauritanie','2026-06-04','2026-09-28','2026-09',2026,62,'Data Management','Mission d\'assistance technique pour la gouvernance des données','Mattel','DP','Infructueux',350000,'Fonds Propres',NULL,334500,NULL,NULL),
(49,'Sénégal','2026-06-20','2026-09-24','2026-09',2026,58,'Digital Transformation','Accompagnement au changement pour le déploiement d\'un nouvel ERP','BCEAO','DP','En cours de préparation',500000,'UNDP',NULL,432100,0.4,172840),
(50,'Gabon','2026-07-04','2026-09-21','2026-09',2026,55,'Data Management','Mission de Data Governance et cartographie des données','SEEG Gabon','AO','Complément d\'information',180000,'UNDP',NULL,176300,0.2,35260),
(51,'Côte d\'Ivoire','2026-04-15','2026-09-20','2026-09',2026,54,'Digital Transformation','Schéma Directeur des SI','UNACOOPEC-CI','AO','Manifestation remise',120000,'GIZ',NULL,113800,0.4,45520),
(52,'Tunisie','2026-05-06','2026-09-19','2026-09',2026,53,'Risk Advisory','Recrutement d\'un cabinet pour l\'audit organisationnel de la DSI','Al Baraka','AMI','Lead',350000,'Fonds Propres','Medianet',317600,NULL,NULL),
(53,'Bénin','2026-05-06','2026-09-18','2026-09',2026,52,'Digital Transformation','AMOA mise en place E-services','Agence Nationale des Transports Terrestres','Avant-vente','En attente du plan de charge',80000,'Kfw',NULL,71800,0.8,57440),
(54,'Mauritanie','2026-04-04','2026-09-15','2026-09',2026,49,'Digital Transformation','Sélection d\'un intégrateur pour un système de gestion documentaire','Agence du Développement Economique Urbain','AO','Infructueux',180000,'Banque Mondiale','GT Consulting',165500,NULL,NULL),
(55,'Mauritanie','2026-05-11','2026-09-14','2026-09',2026,48,'Risk Advisory','Référencement Cyber','Générale de Banque de Mauritanie','Prospection','Opportunité détectée',50000,'Fonds Propres','IMCG',47300,NULL,NULL),
(56,'Bénin','2026-07-16','2026-09-12','2026-09',2026,46,'Digital Transformation','Etude de cadrage pour la mise en place d\'un ERP','Ministère des environnements','DP','Propal shortlistée',120000,'Fonds Propres',NULL,105200,0.6,63120),
(57,'Rwanda','2026-07-12','2026-09-11','2026-09',2026,45,'Data Management','Mission de Data Governance et cartographie des données','Smart Africa','Gré à gré','Offre perdue',120000,'ENABEL','Pragma',107700,NULL,NULL),
(58,'Bénin','2026-06-27','2026-09-07','2026-09',2026,41,'Data Management','Mise en place d\'un tableau de bord de pilotage (Business Intelligence)','Douanes du Bénin','AO','Opportunité détectée',120000,'GIZ','Finetech',102900,NULL,NULL),
(59,'Tunisie','2026-06-30','2026-09-05','2026-09',2026,39,'Digital Transformation','Accompagnement au changement pour le déploiement d\'un nouvel ERP','Office des Œuvres Universitaires pour le Centre (OOUC)','Prospection','Offre remise',80000,'Banque Mondiale','Keyrus',71700,0.8,57360),
(60,'Bénin','2026-04-30','2026-09-04','2026-09',2026,38,'Digital Transformation','Accompagnement à la Transformation Digitale','Ministère de la Santé du Bénin','Avant-vente','Infructueux',1500000,'Fonds Propres',NULL,1334800,NULL,NULL),
(61,'Bénin','2026-05-11','2026-09-04','2026-09',2026,38,'Data Management','Développement d’un modèle de gouvernance du Data center de l’ADETIC','PATN','Prospection','Lead',750000,'Banque Mondiale',NULL,747300,NULL,NULL),
(62,'Burkina Faso','2026-07-12','2026-09-01','2026-09',2026,35,'Digital Transformation','Recrutement d\'un cabinet pour l\'étude de faisabilité de la mise en place d\'un système sécurisé, de sauvegarde et restauration, de gestion de l\'ensemble du système d\'information de l\'INStaD','Instittut National de la Statistique et de la Démographie','AO','Offre perdue',750000,'BEI',NULL,656100,NULL,NULL),
(63,'Tunisie','2026-05-18','2026-09-01','2026-09',2026,35,'Data Management','Besoin : Data ( assainissement des données / BI ) et IA','CEPEX','AMI','En attente du plan de charge',250000,'Fonds Propres',NULL,248300,0.8,198640),
(64,'Togo','2026-05-03','2026-09-01','2026-09',2026,35,'Digital Transformation','Preparation du dossier de referencement CORIS Bank TOGO','CORIS BANK','Avant-vente','Offre signée',1000000,'Fonds Propres','IDVEY',973100,1,973100),
(65,'Tunisie','2026-04-16','2026-08-30','2026-08',2026,33,'Risk Advisory','Politique de Sécurité et la cartographie des risques du Système d\'Information','CNSS','AO','Complément d\'information',1500000,'Fonds Propres',NULL,1279200,0.2,255840),
(66,'Bénin','2026-04-15','2026-08-27','2026-08',2026,30,'Digital Transformation','Recrutement d\'un cabinet de contrôle et coordination des activités d\'installations des salles numériques dans les établissements secondaires','ASIN','DP','Opportunité détectée',1000000,'EU','Medianet',855000,NULL,NULL),
(67,'Tunisie','2026-04-19','2026-08-23','2026-08',2026,26,'Digital Transformation','AMOA SAP','STEG','AMI','Opportunité détectée',500000,'EU','ADDINN',450000,NULL,NULL),
(68,'Tunisie','2026-05-26','2026-08-22','2026-08',2026,25,'Digital Transformation','BZ , Referencement AMOA','Zitouna Banque','AO','Offre signée',80000,'Fonds Propres',NULL,77300,1,77300),
(69,'Tunisie','2026-02-24','2026-08-20','2026-08',2026,23,'Risk Advisory','Audit de sécurité du Système d\'Information','Office du Commerce Tunisien (OCT)','DP','En cours de préparation',1500000,'Banque Mondiale',NULL,1458200,0.4,583280),
(70,'Tunisie','2026-03-20','2026-08-19','2026-08',2026,22,'Data Management','Mission de Data Governance et cartographie des données','Attijari Bank','DP','En cours de qualification',180000,'Fonds Propres','IDVEY',187900,0.2,37580),
(71,'Tunisie','2026-04-27','2026-08-18','2026-08',2026,21,'Digital Transformation','Assistance montée de version d\'Amplitude','Attijari Bank','AMI','Opportunité détectée',1500000,'Fonds Propres',NULL,1479700,NULL,NULL),
(72,'Bénin','2026-06-29','2026-08-16','2026-08',2026,19,'Risk Advisory','Recrutement d\'un consultant pour la définition et la vulgarisation d\'un cadre d\'analyse des risques (objectif EBIOS)','ASIN','DP','Complément d\'information',500000,'ENABEL',NULL,443600,0.2,88720),
(73,'Tunisie','2026-05-02','2026-08-16','2026-08',2026,19,'Risk Advisory','Renforcement des capacités en cybersécurité (formation RSSI)','Enda TAO','DP','En cours de préparation',500000,'Fonds Propres',NULL,506200,0.4,202480),
(74,'Bénin','2026-04-21','2026-08-15','2026-08',2026,18,'Digital Transformation','SDSI : INSTITUT NATIONAL DE LA JEUNESSE ET DES SPORTS','INJS','DP','Lead',80000,'Suisse','Medianet',80500,NULL,NULL),
(75,'Mauritanie','2026-05-14','2026-08-14','2026-08',2026,17,'Risk Advisory','Mise en conformité avec la réglementation sur la protection des données','Agence du Développement Economique Urbain','Consultation','Offre gagnée',80000,'Banque Mondiale',NULL,79200,1,79200),
(76,'Sénégal','2026-05-28','2026-08-08','2026-08',2026,11,'Risk Advisory','sélection d\'un prestataire en vue d\'accompagner la BCEAO dans la mise en place d’un plan de réponse aux incidents de cybersécurité','BCEAO','AO','Offre perdue',180000,'AFD','Keyrus',170800,NULL,NULL),
(77,'Mauritanie','2026-03-08','2026-08-06','2026-08',2026,9,'Digital Transformation','Etude de faisabilité pour la migration vers le Cloud','WARDIP','DP','Offre perdue',750000,'ENABEL','Hedal Consulting',767200,NULL,NULL),
(78,'Maroc','2026-04-05','2026-08-03','2026-08',2026,6,'Risk Advisory','Accompagnement Conformité Instriction 21/2024','BMCI','DP','Complément d\'information',250000,'Fonds Propres','GT Consulting',222100,0.2,44420),
(79,'Côte d\'Ivoire','2026-05-15','2026-08-02','2026-08',2026,5,'Digital Transformation','Feuille de route ERP','GESTOCI','Gré à gré','Lead',250000,'UNDP',NULL,212600,NULL,NULL),
(80,'Tunisie','2026-04-03','2026-07-29','2026-07',2026,1,'Data Management','Data Governance','BNA','Gré à gré','Non shortlisté',500000,'Fonds Propres',NULL,523200,NULL,NULL),
(81,'Bénin','2026-03-16','2026-07-27','2026-07',2026,-1,'Digital Transformation','Sélection d’un consultant (cabinet) charge de la revue des processus internes actuels et identification des processus à digitaliser pour ameliorer l’efficacite de l’ANADEC','ANADEC','AO','Manifestation remise',750000,'BAD',NULL,689000,0.4,275600),
(82,'Bénin','2026-05-17','2026-07-26','2026-07',2026,-2,'Risk Advisory','Recrutement d\'un consultant pour l\'élaboration des outils de contrôle interne et de mitigation des risques (cartographie des risques, manuels de procédures, guides d\'audit, etc.) au profit du Secrétariat Général du Ministère des Finances','Projet de Gouvernement Économique et de Délivrance des Services au Bénin (PGEDS)','AMI','Offre gagnée',1000000,'AFD','Expertise Advisors',900600,1,900600),
(83,'Tunisie','2026-02-14','2026-07-24','2026-07',2026,-4,'Risk Advisory','Renforcement des capacités en cybersécurité (formation RSSI)','ITCEQ','AMI','Propal shortlistée',120000,'Fonds Propres','Medianet',121500,0.6,72900),
(84,'Côte d\'Ivoire','2026-03-25','2026-07-23','2026-07',2026,-5,'Digital Transformation','Mise en place d’un catalogue des services DSI','CDC-CI','Avant-vente','Offre signée',1500000,'ENABEL','Keyrus',1464500,1,1464500),
(85,'Côte d\'Ivoire','2026-02-23','2026-07-22','2026-07',2026,-6,'Digital Transformation','Accompagnement à la Transformation Digitale','CIE Côte d\'Ivoire','AO','Offre gagnée',1500000,'Kfw',NULL,1286800,1,1286800),
(86,'Bénin','2026-04-07','2026-07-11','2026-07',2026,-17,'Risk Advisory','Réalisation de formation certifiante au profit de vingt cinq (25) RSSI','ASIN','AO','Manif shortlistée',250000,'ENABEL','Keyrus',250900,0.6,150540),
(87,'Mauritanie','2026-05-10','2026-07-06','2026-07',2026,-22,'Data Management','Mission d\'assistance technique pour la gouvernance des données','SOMELEC','DP','Lead',500000,'Fonds Propres','IDVEY',495000,NULL,NULL),
(88,'Tunisie','2026-01-25','2026-07-04','2026-07',2026,-24,'Digital Transformation','analyse du système applicatif et cartographie SI','STB','AO','Manifestation remise',50000,'Fonds Propres',NULL,48100,0.4,19240),
(89,'Mali','2026-02-21','2026-07-02','2026-07',2026,-26,'Risk Advisory','Recrutement d\'un consultant pour la cartographie des risques IT','GIMTEL','AMI','Manif shortlistée',120000,'Fonds Propres',NULL,104000,0.6,62400),
(90,'Sénégal','2026-03-17','2026-07-02','2026-07',2026,-26,'Digital Transformation','Lot 3 : Étude de cadrage et spécifications techniques pour la Plateforme Santé Infantile et Maternelle (PSIM)','UNICEF','AO','En attente du plan de charge',50000,'ENABEL',NULL,44900,0.8,35920),
(91,'Tunisie','2026-02-06','2026-06-30','2026-06',2026,-28,'Risk Advisory','Recrutement d\'un consultant pour la cartographie des risques IT','STEG','DP','Offre perdue',50000,'ENABEL','ADDINN',48900,NULL,NULL),
(92,'Tunisie','2026-01-09','2026-06-27','2026-06',2026,-31,'Data Management','Uses Cases IA','DIGITECH','AO','En attente du plan de charge',120000,'Fonds Propres',NULL,123900,0.8,99120),
(93,'Bénin','2026-03-30','2026-06-24','2026-06',2026,-34,'Risk Advisory','Assistance à l\'audit des systèmes d\'information','CDC Bénin','DP','En cours de préparation',750000,'GIZ',NULL,643000,0.4,257200),
(94,'France','2026-05-25','2026-06-23','2026-06',2026,-35,'Digital Transformation','Architecte Cloud & Infrastructure GCP (H/F) OffShore','Dvt FR','AO','Offre perdue',1500000,'Fonds Propres','Medianet',1531700,NULL,NULL),
(95,'Niger','2026-01-11','2026-06-23','2026-06',2026,-35,'Risk Advisory','Renforcement des capacités en cybersécurité (formation RSSI)','Banque Agricole du Niger','Consultation','Manifestation remise',180000,'EU',NULL,168100,0.4,67240),
(96,'Mauritanie','2026-04-29','2026-06-23','2026-06',2026,-35,'Risk Advisory','PCA','Mattel','DP','Complément d\'information',1000000,'Fonds Propres',NULL,1050000,0.2,210000),
(97,'Mauritanie','2026-02-22','2026-06-23','2026-06',2026,-35,'Digital Transformation','Elaboration d’un schéma directeur du système d’information au profit de l’Agence du Développement Economique Urbain (ADEU)','Agence du Développement Economique Urbain','AO','Offre remise',750000,'GIZ',NULL,786300,0.8,629040),
(98,'Bénin','2026-02-11','2026-06-22','2026-06',2026,-36,'Digital Transformation','Elaboration du Schéma Directeur des Systèmes d\'Information','Agence de Développement de Sèmè City','DP','Lead',500000,'AFD',NULL,498800,NULL,NULL),
(99,'Tunisie','2026-04-03','2026-06-22','2026-06',2026,-36,'Digital Transformation','Accompagnement au changement pour le déploiement d\'un nouvel ERP','TunisRe','AMI','En cours de qualification',350000,'Fonds Propres',NULL,329900,0.2,65980),
(100,'Tunisie','2026-04-01','2026-06-17','2026-06',2026,-41,'Risk Advisory','Renforcement des capacités en cybersécurité (formation RSSI)','API','DP','Offre perdue',350000,'GIZ','IMCG',351200,NULL,NULL),
(101,'Comores','2026-05-13','2026-06-15','2026-06',2026,-43,'Risk Advisory','Elaboration du Plan de Continuité d\'Activité (PCA)','Banque Postale Comores','AO','Propal shortlistée',350000,'Fonds Propres','IDVEY',325500,0.6,195300),
(102,'Bénin','2026-03-22','2026-06-11','2026-06',2026,-47,'Digital Transformation','SDSI','ONEAD','DP','Lead',50000,'ENABEL',NULL,50500,NULL,NULL),
(103,'Tunisie','2026-02-01','2026-06-09','2026-06',2026,-49,'Risk Advisory','Renforcement des capacités en cybersécurité (formation RSSI)','API','AO','Propal shortlistée',350000,'UNDP','IDVEY',338500,0.6,203100),
(104,'Bénin','2026-01-23','2026-06-09','2026-06',2026,-49,'Digital Transformation','Elaboration du Schéma Directeur des Systèmes d\'Information','Société des Aéroports du Bénin','AO','Lead',250000,'BEI','FTHM',213100,NULL,NULL),
(105,'Tunisie','2026-03-26','2026-06-08','2026-06',2026,-50,'Risk Advisory','Mise en place d\'un Centre Opérationnel de Sécurité (SOC)','SNCFT','AMI','En cours de qualification',250000,'UNDP','Expertise Advisors',215400,0.2,43080),
(106,'Tunisie','2026-03-28','2026-06-08','2026-06',2026,-50,'Digital Transformation','SDSI ( Refresh)','BTK','Gré à gré','En cours de préparation',50000,'Fonds Propres','IMCG',47200,0.4,18880),
(107,'Bénin','2026-02-08','2026-06-07','2026-06',2026,-51,'Risk Advisory','Audit de sécurité du Système d\'Information','DGI','AMI','Lead',750000,'EU','Medianet',720100,NULL,NULL),
(108,'Tunisie','2026-03-25','2026-06-06','2026-06',2026,-52,'Digital Transformation','Etude de faisabilité pour la migration vers le Cloud','Office du Commerce','DP','NO GO',350000,'EU',NULL,366900,NULL,NULL),
(109,'Tchad','2026-03-18','2026-06-05','2026-06',2026,-53,'Digital Transformation','Etude pour la conception et l\'installation d\'un SI pour la centralisation et l\'analyse des budgets et comptes des collectivités territoriales','Projet d\'Appui à la Decentralisation et au Développement des Villes','Gré à gré','Offre signée',80000,'Suisse',NULL,76300,1,76300),
(110,'Tunisie','2026-02-20','2026-06-04','2026-06',2026,-54,'Digital Transformation','Projet Monitoring des alertes','Attijari Bank','Gré à gré','Offre remise',350000,'Fonds Propres',NULL,358000,0.8,286400),
(111,'Bénin','2026-03-23','2026-06-01','2026-06',2026,-57,'Digital Transformation','Etude SIGE et Constitution du référentiel EFTP','ASIN','DP','En cours de qualification',180000,'ENABEL',NULL,173200,0.2,34640),
(112,'Tunisie','2026-04-02','2026-05-25','2026-05',2026,-64,'Digital Transformation','Assistance montée de version d\'Amplitude','Attijari Bank','DP','En attente du plan de charge',1500000,'Fonds Propres',NULL,1333200,0.8,1066560),
(113,'Tunisie','2026-01-11','2026-05-21','2026-05',2026,-68,'Risk Advisory','Audit de sécurité du Système d\'Information','INTT','AO','Opportunité détectée',350000,'EU',NULL,357400,NULL,NULL),
(114,'Mauritanie','2026-02-04','2026-05-17','2026-05',2026,-72,'Digital Transformation','SDSI','Générale de Banque de Mauritanie','AO','Manif shortlistée',1500000,'Fonds Propres','IMCG',1544900,0.6,926940),
(115,'Mali','2026-03-01','2026-05-12','2026-05',2026,-77,'Risk Advisory','Recrutement d\'un consultant pour la cartographie des risques IT','GIMTEL','DP','Propal shortlistée',120000,'Fonds Propres',NULL,103800,0.6,62280),
(116,'Mauritanie','2025-12-14','2026-05-09','2026-05',2026,-80,'Digital Transformation','Accompagnement à la Transformation Digitale','WARDIP','DP','Manifestation remise',750000,'Banque Mondiale',NULL,701700,0.4,280680),
(117,'Tunisie','2026-04-02','2026-05-09','2026-05',2026,-80,'Risk Advisory','Audit de sécurité du Système d\'Information','Carrefour - UHD','AO','Lead',250000,'Fonds Propres',NULL,218400,NULL,NULL),
(118,'Tunisie','2026-03-08','2026-05-08','2026-05',2026,-81,'Digital Transformation','Etude stratégique pour la transformation digitale et plan opérationnel','OMMP','Consultation','Lead',180000,'Kfw','IDVEY',171500,NULL,NULL),
(119,'Tunisie','2026-02-25','2026-05-06','2026-05',2026,-83,'Data Management','Elaboration d\'une feuille de route pour l\'intelligence artificielle','Poste Tunisienne','Avant-vente','Propal shortlistée',500000,'Banque Mondiale',NULL,445100,0.6,267060),
(120,'Gabon','2026-01-02','2026-05-05','2026-05',2026,-84,'Risk Advisory','Audit SI','Petro Gabon','AO','Manif shortlistée',120000,'Fonds Propres','Expertise Advisors',111000,0.6,66600),
(121,'Tunisie','2025-12-24','2026-05-04','2026-05',2026,-85,'Digital Transformation','Accompagnement au changement pour le déploiement d\'un nouvel ERP','BNA','Consultation','En cours de qualification',80000,'Fonds Propres',NULL,82100,0.2,16420),
(122,'Tunisie','2026-03-10','2026-05-02','2026-05',2026,-87,'Digital Transformation','Customer Experience','BTK','Consultation','Lead',250000,'Fonds Propres',NULL,233300,NULL,NULL),
(123,'Mauritanie','2026-03-27','2026-05-01','2026-05',2026,-88,'Risk Advisory','SMSI','Mattel','Prospection','Manifestation remise',1000000,'Fonds Propres',NULL,973400,0.4,389360),
(124,'Rwanda','2026-03-17','2026-04-29','2026-04',2026,-90,'Data Management','Recruitment of a Consultancy Firm or Consortium for the Development of Benin\'s National Data Strategy','Smart Africa','Prospection','Lead',180000,'Banque Mondiale','Keyrus',157300,NULL,NULL),
(125,'Bénin','2026-03-12','2026-04-25','2026-04',2026,-94,'Digital Transformation','Sélection d\'un intégrateur pour un système de gestion documentaire','ASIN','AO','Offre remise',500000,'BAD',NULL,452300,0.8,361840),
(126,'Burkina Faso','2026-02-22','2026-04-22','2026-04',2026,-97,'Risk Advisory','Mise en conformité avec la réglementation sur la protection des données','SONABEL','AMI','Offre signée',1000000,'Fonds Propres',NULL,1024100,1,1024100),
(127,'Bénin','2026-03-09','2026-04-20','2026-04',2026,-99,'Risk Advisory','Audit Organisationnel des Systèmes d\'Information des Direction des Systèmes d\'Informations des ministères et structures sous tutelle afin d\'optimiser le support ASIN et augmenter l\'autonomie du Ministère','ASIN','AO','Offre signée',350000,'ENABEL','DWT',335200,1,335200),
(128,'Bénin','2025-12-31','2026-04-20','2026-04',2026,-99,'Risk Advisory','Assistance à l\'audit des systèmes d\'information','CDC Bénin','AMI','En cours de qualification',750000,'GIZ',NULL,745100,0.2,149020),
(129,'Mauritanie','2026-02-15','2026-04-20','2026-04',2026,-99,'Digital Transformation','Elaboration d\'un Diagnostic du SI','Mauritania Airlines','Consultation','Infructueux',1000000,'Fonds Propres',NULL,885100,NULL,NULL),
(130,'Bénin','2026-03-24','2026-04-19','2026-04',2026,-100,'Digital Transformation','Etude de cadrage pour la mise en place d\'un ERP','Douanes du Bénin','AMI','En cours de qualification',180000,'GIZ','Keyrus',175000,0.2,35000),
(131,'Tunisie','2025-12-21','2026-04-14','2026-04',2026,-105,'Risk Advisory','lot 1 : audit de la sécurité du système d’information de l’INT','INTT','AO','Non shortlisté',750000,'EU','IDVEY',708600,NULL,NULL),
(132,'Côte d\'Ivoire','2025-12-07','2026-04-13','2026-04',2026,-106,'Risk Advisory','Mise en œuvre du PCA','CDC-CI','Avant-vente','Offre gagnée',1000000,'AFD',NULL,875100,1,875100),
(133,'Bénin','2025-11-12','2026-04-11','2026-04',2026,-108,'Digital Transformation','SDSI','Ministère du tourisme','AMI','Offre perdue',1000000,'Suisse',NULL,969200,NULL,NULL),
(134,'Tunisie','2026-02-04','2026-04-09','2026-04',2026,-110,'Risk Advisory','Elaboration de la Politique de Sécurité du Système d\'Inforation (PSSI) et Plan de Continuité d\'Activité (PCA) de l\'Institut Tunisien de la Compétitivité et des Etudes Quantitatives','ITCEQ','AO','Lead',80000,'BAD','GT Consulting',77900,NULL,NULL),
(135,'Tunisie','2026-02-01','2026-04-06','2026-04',2026,-113,'Data Management','Gouvernance des données et systèmes d\'information','BTK','Gré à gré','Complément d\'information',1000000,'Fonds Propres','ADDINN',925800,0.2,185160),
(136,'Côte d\'Ivoire','2026-01-03','2026-04-04','2026-04',2026,-115,'Risk Advisory','PCA : Analyse de l\'existant + proposition d\'amélioration','Petro Ivoire','Avant-vente','Lead',80000,'Fonds Propres',NULL,70200,NULL,NULL),
(137,'Tunisie','2025-10-27','2026-04-01','2026-04',2026,-118,'Digital Transformation','Optimisation des processus','BTK','AMI','Manif shortlistée',50000,'Fonds Propres',NULL,50700,0.6,30420),
(138,'Burundi','2025-10-28','2026-03-31','2026-03',2026,-119,'Risk Advisory','Assistance technique pour le recrutement d’un Bureau spécialisé dans l’implémentation d’un système de Management de la Sécurité de l’Information (SMSI) à l’Office Burundais des Recettes (OBR)','PAFEN','AMI','Offre perdue',120000,'EU','IDVEY',114300,NULL,NULL),
(139,'Bénin','2025-10-07','2026-03-31','2026-03',2026,-119,'Digital Transformation','Etude de cadrage pour la mise en place d\'un ERP','INJS','Consultation','Complément d\'information',750000,'Fonds Propres','Finetech',673600,0.2,134720),
(140,'Mali','2025-10-13','2026-03-26','2026-03',2026,-124,'Data Management','Elaboration d\'une feuille de route pour l\'intelligence artificielle','Office National de l\'Electricité du Mali','DP','Offre perdue',1500000,'AFD','Finetech',1417400,NULL,NULL),
(141,'Gabon','2025-09-28','2026-03-23','2026-03',2026,-127,'Digital Transformation','Assistance à Maîtrise d\'Ouvrage (AMOA) pour la refonte du SI','Petro Gabon','DP','Offre signée',750000,'Fonds Propres',NULL,769700,1,769700),
(142,'Mali','2025-11-22','2026-03-23','2026-03',2026,-127,'Digital Transformation','Feuille de route Mansa Bank','Mansa Bank','AO','Complément d\'information',250000,'Fonds Propres',NULL,231200,0.2,46240),
(143,'Bénin','2025-10-07','2026-03-22','2026-03',2026,-128,'Data Management','Etude de qualification des serveurs et applications et renforcement des capacités pour la migration des systèmes d\'informations vers le Data Center National','ASIN','Gré à gré','Offre remise',500000,'GIZ',NULL,444000,0.8,355200),
(144,'Bénin','2025-12-12','2026-03-22','2026-03',2026,-128,'Risk Advisory','Etudes préalables à l’implémentation des sous-projets et l’élaboration des termes de référence et des cahiers des charges pour la mise en œuvre de la composante « renforcement de la sécurité numérique','PATN','Consultation','Offre gagnée',250000,'AFD',NULL,228500,1,228500),
(145,'Côte d\'Ivoire','2025-09-24','2026-03-22','2026-03',2026,-128,'Risk Advisory','Mise en conformité avec la réglementation sur la protection des données','Petro Ivoire','DP','Infructueux',80000,'Fonds Propres','Medianet',70300,NULL,NULL),
(146,'Tunisie','2025-12-23','2026-03-17','2026-03',2026,-133,'Risk Advisory','Analyse des risques IT','STB','Gré à gré','Propal shortlistée',750000,'Fonds Propres',NULL,784200,0.6,470520),
(147,'Côte d\'Ivoire','2026-02-17','2026-03-17','2026-03',2026,-133,'Risk Advisory','Audit de sécurité du Système d\'Information','SODECI','AMI','En attente du plan de charge',750000,'UNDP','ADDINN',760600,0.8,608480),
(148,'Mauritanie','2026-01-06','2026-03-17','2026-03',2026,-133,'Data Management','Mission d\'assistance technique pour la gouvernance des données','SOMELEC','AMI','Offre perdue',500000,'Fonds Propres','IDVEY',466000,NULL,NULL),
(149,'Tunisie','2026-01-25','2026-03-14','2026-03',2026,-136,'Data Management','Besoin : Data ( assainissement des données / BI ) et IA','CEPEX','DP','Offre perdue',250000,'Fonds Propres',NULL,223200,NULL,NULL),
(150,'Burkina Faso','2026-01-19','2026-03-14','2026-03',2026,-136,'Data Management','Mission de Data Governance et cartographie des données','Instittut National de la Statistique et de la Démographie','Prospection','Complément d\'information',1000000,'UNDP',NULL,945300,0.2,189060),
(151,'Bénin','2025-10-13','2026-03-13','2026-03',2026,-137,'Risk Advisory','Recrutement d\'un cabinet pour l\'audit organisationnel de la DSI','Port Autonome de Cotonou','AO','Lead',1000000,'GIZ','Expertise Advisors',1025700,NULL,NULL),
(152,'Tunisie','2025-09-26','2026-03-11','2026-03',2026,-139,'Digital Transformation','Accompagnement au changement pour le déploiement d\'un nouvel ERP','TunisRe','DP','Offre signée',350000,'Fonds Propres',NULL,360400,1,360400),
(153,'Bénin','2026-01-23','2026-03-03','2026-03',2026,-147,'Risk Advisory','Elaboration du Plan de Continuité d\'Activité (PCA)','Agence de Développement de Sèmè City','Prospection','Propal shortlistée',120000,'EU',NULL,112000,0.6,67200),
(154,'France','2025-12-01','2026-03-01','2026-03',2026,-149,'Risk Advisory','Recrutement d\'un consultant pour la cartographie des risques IT','Orange Bank','DP','En attente du plan de charge',1500000,'Fonds Propres',NULL,1536700,0.8,1229360),
(155,'Tunisie','2025-10-14','2026-02-24','2026-02',2026,-154,'Digital Transformation','Etude d\'urbanisation du Système d\'Information','SNCFT','AMI','Manifestation remise',250000,'GIZ','IDVEY',234200,0.4,93680),
(156,'Tunisie','2026-01-29','2026-02-23','2026-02',2026,-155,'Risk Advisory','Recrutement d\'un consultant pour la cartographie des risques IT','API','DP','Offre perdue',1000000,'ENABEL',NULL,965400,NULL,NULL),
(157,'Tunisie','2025-11-12','2026-02-23','2026-02',2026,-155,'Digital Transformation','Etude de cadrage pour la mise en place d\'un ERP','Zitouna Banque','Consultation','Offre gagnée',50000,'Fonds Propres','Keyrus',43400,1,43400),
(158,'Mauritanie','2026-01-19','2026-02-22','2026-02',2026,-156,'Data Management','Mission d\'assistance technique pour la gouvernance des données','Mattel','AMI','Lead',350000,'Fonds Propres',NULL,307400,NULL,NULL),
(159,'France','2025-09-02','2026-02-21','2026-02',2026,-157,'Digital Transformation','ITOPS OffShore','Dvt FR','AO','Propal shortlistée',250000,'Fonds Propres',NULL,240500,0.6,144300),
(160,'Bénin','2025-10-13','2026-02-19','2026-02',2026,-159,'Risk Advisory','Recrutrement d\'un prestataire pour la finalisation de l\'Implémentation du Système de Management de Sécurité de l\'Information (SMSI) : ISO 27001','Société des Aéroports du Bénin','AMI','Manifestation remise',500000,'BAD',NULL,425800,0.4,170320),
(161,'Tunisie','2025-12-04','2026-02-18','2026-02',2026,-160,'Risk Advisory','Refonte PCA','Zitouna Banque','Consultation','Offre signée',80000,'Fonds Propres','FTHM',75800,1,75800),
(162,'France','2025-10-12','2026-02-18','2026-02',2026,-160,'Risk Advisory','Recrutement d\'un consultant pour la cartographie des risques IT','Orange Bank','AMI','Offre perdue',1500000,'Fonds Propres',NULL,1373800,NULL,NULL),
(163,'Tunisie','2025-12-04','2026-02-16','2026-02',2026,-162,'Risk Advisory','Mise en conformité avec la réglementation sur la protection des données','TunisRe','Prospection','Manifestation remise',500000,'Fonds Propres','GT Consulting',466000,0.4,186400),
(164,'Tunisie','2025-11-10','2026-02-14','2026-02',2026,-164,'Digital Transformation','Support digital transformation of public services in Tunisia','Banque Mondiale','AO','Propal shortlistée',1000000,'Banque Mondiale',NULL,899100,0.6,539460),
(165,'Mali','2025-10-13','2026-02-07','2026-02',2026,-171,'Digital Transformation','Etude de cadrage pour la mise en place d\'un ERP','Office du Commerce','Avant-vente','En cours de qualification',350000,'Suisse',NULL,343200,0.2,68640),
(166,'Gabon','2025-12-28','2026-02-03','2026-02',2026,-175,'Data Management','Mission d\'assistance technique pour la gouvernance des données','Petro Gabon','Consultation','Complément d\'information',500000,'Fonds Propres','Keyrus',496400,0.2,99280),
(167,'Côte d\'Ivoire','2025-08-05','2026-01-31','2026-01',2026,-178,'Risk Advisory','Mise en place d\'un Centre Opérationnel de Sécurité (SOC)','CDC-CI','AO','Offre perdue',350000,'BAD',NULL,331300,NULL,NULL),
(168,'Togo','2025-09-19','2026-01-31','2026-01',2026,-178,'Risk Advisory','PCA','CRRH','Prospection','Offre signée',180000,'Fonds Propres','Expertise Advisors',185800,1,185800),
(169,'Côte d\'Ivoire','2025-08-10','2026-01-29','2026-01',2026,-180,'Risk Advisory','Mise en conformité avec la réglementation sur la protection des données','CIE Côte d\'Ivoire','AO','Offre perdue',180000,'BEI',NULL,186800,NULL,NULL),
(170,'Bénin','2025-09-13','2026-01-27','2026-01',2026,-182,'Digital Transformation','Etudes préalables à l’implémentation et l’élaboration des cahiers de charges pour la mise en œuvre du sous-projet « système d’information de gestion de l’enseignement supérieur (SIGES)','PATN','Prospection','Opportunité détectée',120000,'Suisse','ADDINN',105400,NULL,NULL),
(171,'France','2025-08-18','2026-01-25','2026-01',2026,-184,'Digital Transformation','Cellule référenceent et gestion des PF','Dvt FR','AO','Offre gagnée',350000,'Fonds Propres',NULL,327400,1,327400),
(172,'Côte d\'Ivoire','2025-09-04','2026-01-21','2026-01',2026,-188,'Digital Transformation','Etude d\'urbanisation du Système d\'Information','SODECI','DP','Offre perdue',1000000,'Fonds Propres','Keyrus',974400,NULL,NULL),
(173,'Bénin','2025-10-05','2026-01-17','2026-01',2026,-192,'Digital Transformation','SDSI','SBEE','AO','Offre perdue',1000000,'Banque Mondiale','GT Consulting',1043700,NULL,NULL),
(174,'Bénin','2025-10-26','2026-01-12','2026-01',2026,-197,'Risk Advisory','Recrutrement d\'un prestataire pour la finalisation de l\'Implémentation du Système de Management de Sécurité de l\'Information (SMSI) : ISO 27001','Société des Aéroports du Bénin','DP','Opportunité détectée',500000,'BAD',NULL,465400,NULL,NULL),
(175,'Bénin','2025-08-20','2026-01-10','2026-01',2026,-199,'Risk Advisory','AMOA Cybersécurité','SBEE','Gré à gré','En cours de qualification',750000,'GIZ',NULL,660600,0.2,132120),
(176,'Tunisie','2025-11-27','2026-01-07','2026-01',2026,-202,'Risk Advisory','Recrutement d\'un cabinet pour l\'audit organisationnel de la DSI','TunisRe','Gré à gré','Offre signée',120000,'Fonds Propres',NULL,120800,1,120800),
(177,'Bénin','2025-11-24','2026-01-02','2026-01',2026,-207,'Digital Transformation','Assistance à Maîtrise d\'Ouvrage (AMOA) pour la refonte du SI','Agence Nationale des Transports Terrestres','AMI','Complément d\'information',500000,'EU',NULL,524100,0.2,104820),
(178,'Sénégal','2025-12-03','2026-01-01','2026-01',2026,-208,'Digital Transformation','Etude de faisabilité pour la migration vers le Cloud','BCEAO','Consultation','Non shortlisté',80000,'Kfw',NULL,74700,NULL,NULL),
(179,'Bénin','2025-08-10','2025-12-28','2025-12',2025,-212,'Digital Transformation','AMOA , Cahier des charges application backoffice','Ministère des environnements','AO','Hors scope',80000,'AFD',NULL,78100,NULL,NULL),
(180,'Bénin','2025-11-15','2025-12-27','2025-12',2025,-213,'Risk Advisory','Mise en Place SIEM','SBEE','Prospection','Non shortlisté',80000,'GIZ',NULL,73200,NULL,NULL),
(181,'Maroc','2025-11-09','2025-12-26','2025-12',2025,-214,'Risk Advisory','Elaboration du Plan de Continuité d\'Activité (PCA)','BMCI','DP','Non shortlisté',80000,'Fonds Propres','Expertise Advisors',74900,NULL,NULL),
(182,'Tunisie','2025-10-26','2025-12-21','2025-12',2025,-219,'Data Management','Paulina, Data Management','Paulina','Prospection','Offre perdue',750000,'Fonds Propres',NULL,717800,NULL,NULL),
(183,'Tunisie','2025-07-21','2025-12-20','2025-12',2025,-220,'Risk Advisory','Recrutement d\'un cabinet pour l\'audit organisationnel de la DSI','Al Baraka','DP','Offre gagnée',350000,'Fonds Propres','Medianet',329000,1,329000),
(184,'Bénin','2025-06-28','2025-12-17','2025-12',2025,-223,'Risk Advisory','Élaboration du document de politique de sécurité des systèmes d\'informations de la SBIR','Société Béninoise de Radio Diffusion','DP','Infructueux',250000,'Banque Mondiale',NULL,217800,NULL,NULL),
(185,'Bénin','2025-07-15','2025-12-03','2025-12',2025,-237,'Digital Transformation','Sélection d\'un cabinet pour élaborer le plan stratégique de Sèmè City sur 5 ans','Agence de Développement de Sèmè City','AO','Offre signée',180000,'Fonds Propres',NULL,168000,1,168000),
(186,'Comores','2025-08-11','2025-12-02','2025-12',2025,-238,'Digital Transformation','Mise à jour de l offre SIRH','Banque Postale Comores','AO','NO GO',1000000,'Fonds Propres',NULL,971700,NULL,NULL),
(187,'Sénégal','2025-08-30','2025-11-27','2025-11',2025,-243,'Digital Transformation','Accompagnement à la Transformation Digitale','Air Sénégal','Prospection','Offre signée',80000,'Suisse','FTHM',79800,1,79800),
(188,'Tunisie','2025-05-30','2025-11-26','2025-11',2025,-244,'Digital Transformation','Sélection d\'un intégrateur pour un système de gestion documentaire','Carrefour - UHD','AO','Offre perdue',1000000,'Fonds Propres',NULL,957900,NULL,NULL),
(189,'Côte d\'Ivoire','2025-06-26','2025-11-25','2025-11',2025,-245,'Digital Transformation','Etude d\'urbanisation du Système d\'Information','SODECI','AMI','Offre signée',1000000,'Fonds Propres','Keyrus',980700,1,980700),
(190,'Bénin','2025-06-30','2025-11-24','2025-11',2025,-246,'Digital Transformation','Recrutement d’un cabinet pour la coordination, le suivi et le contrôle des projets RBER phase 3 et Connectivité des structures sanitaires','ASIN','Gré à gré','Offre gagnée',1500000,'UNDP',NULL,1372400,1,1372400),
(191,'Bénin','2025-06-14','2025-11-22','2025-11',2025,-248,'Risk Advisory','Elaboration de la politique de sécurisation des systèmes d\'information (PSSI) du FNDA','Fonds National de Développement Agricole','Prospection','Offre gagnée',50000,'UNDP','IDVEY',47800,1,47800),
(192,'Bénin','2025-09-10','2025-11-20','2025-11',2025,-250,'Risk Advisory','Recrutement d\'un consultant pour assurer l\'audit des effectifs et des compétences des agents de la Fonction Publique','Projet de Gouvernement Économique et de Délivrance des Services au Bénin (PGEDS)','DP','Offre signée',350000,'Banque Mondiale',NULL,323800,1,323800),
(193,'Bénin','2025-07-30','2025-11-20','2025-11',2025,-250,'Digital Transformation','SDSI + AMOA','Cours des Comptes','Consultation','Offre signée',250000,'UNDP','Hedal Consulting',223600,1,223600),
(194,'Mali','2025-06-01','2025-11-17','2025-11',2025,-253,'Data Management','Elaboration d\'une feuille de route pour l\'intelligence artificielle','Office National de l\'Electricité du Mali','AMI','Infructueux',1500000,'AFD','Finetech',1375700,NULL,NULL),
(195,'Bénin','2025-10-01','2025-11-17','2025-11',2025,-253,'Digital Transformation','SDSI : INSTITUT NATIONAL DE LA JEUNESSE ET DES SPORTS','INJS','AMI','NO GO',80000,'Suisse','Medianet',70500,NULL,NULL),
(196,'Bénin','2025-05-24','2025-11-14','2025-11',2025,-256,'Digital Transformation','Elaboration de la stratégie de données pour des collectivités locales','ASIN','DP','Infructueux',50000,'ENABEL',NULL,51600,NULL,NULL),
(197,'Mauritanie','2025-09-03','2025-11-11','2025-11',2025,-259,'Digital Transformation','Etude de cadrage pour la mise en place d\'un ERP','SOMELEC','Consultation','Offre gagnée',50000,'Fonds Propres','ADDINN',44000,1,44000),
(198,'Tunisie','2025-07-12','2025-11-10','2025-11',2025,-260,'Risk Advisory','Renforcement des capacités en cybersécurité (formation RSSI)','Tunisie Telecom','DP','Offre gagnée',80000,'BAD','Pragma',74900,1,74900),
(199,'Mauritanie','2025-08-03','2025-11-08','2025-11',2025,-262,'Digital Transformation','Accompagnement à la Transformation Digitale','WARDIP','AMI','Offre gagnée',750000,'Banque Mondiale',NULL,758200,1,758200),
(200,'Tunisie','2025-06-14','2025-11-08','2025-11',2025,-262,'Digital Transformation','Sélection d\'un intégrateur pour un système de gestion documentaire','Enda TAO','AO','Offre signée',750000,'Fonds Propres','Expertise Advisors',697700,1,697700),
(201,'Tunisie','2025-10-07','2025-11-06','2025-11',2025,-264,'Digital Transformation','Accompagnement au changement pour le déploiement d\'un nouvel ERP','BTK','Gré à gré','Offre gagnée',750000,'Fonds Propres','IMCG',659300,1,659300),
(202,'Mauritanie','2025-07-01','2025-10-29','2025-10',2025,-272,'Digital Transformation','Etude de faisabilité pour la migration vers le Cloud','WARDIP','AMI','Infructueux',750000,'ENABEL','Hedal Consulting',780300,NULL,NULL),
(203,'Tunisie','2025-06-27','2025-10-27','2025-10',2025,-274,'Digital Transformation','Etude de cadrage pour la mise en place d\'un ERP','Zitouna Banque','DP','Infructueux',250000,'Fonds Propres',NULL,219900,NULL,NULL),
(204,'Mauritanie','2025-09-23','2025-10-26','2025-10',2025,-275,'Digital Transformation','Accompagnement à la Transformation Digitale','Mauritania Airlines','DP','Offre gagnée',350000,'Fonds Propres','IDVEY',330500,1,330500),
(205,'Cameroun','2025-07-17','2025-10-22','2025-10',2025,-279,'Data Management','Mise en place d\'un tableau de bord de pilotage (Business Intelligence)','GIMAC','AO','Non shortlisté',500000,'Fonds Propres',NULL,465800,NULL,NULL),
(206,'Bénin','2025-06-05','2025-10-21','2025-10',2025,-280,'Digital Transformation','Etude de cadrage pour la mise en place d\'un ERP','Douanes du Bénin','DP','Offre perdue',180000,'GIZ','Keyrus',177300,NULL,NULL),
(207,'Tunisie','2025-09-13','2025-10-20','2025-10',2025,-281,'Digital Transformation','Soutien à la transformation numérique des services publics en Tunisie','Banque Mondiale','AO','Hors scope',180000,'Banque Mondiale',NULL,171000,NULL,NULL),
(208,'Maroc','2025-08-09','2025-10-19','2025-10',2025,-282,'Risk Advisory','Audit PCA','BMCI','Gré à gré','Hors scope',1500000,'Fonds Propres','Hedal Consulting',1302800,NULL,NULL),
(209,'Mauritanie','2025-06-12','2025-10-18','2025-10',2025,-283,'Risk Advisory','PCA','Générale de Banque de Mauritanie','Prospection','Non shortlisté',180000,'Fonds Propres','FTHM',156300,NULL,NULL),
(210,'Maroc','2025-09-06','2025-10-14','2025-10',2025,-287,'Risk Advisory','Accompagnement Conformité Instriction 21/2024','BMCI','AMI','Offre perdue',250000,'Fonds Propres','GT Consulting',245900,NULL,NULL),
(211,'Tunisie','2025-08-22','2025-10-11','2025-10',2025,-290,'Digital Transformation','Etude de faisabilité pour la migration vers le Cloud','DIGITECH','Consultation','Offre signée',50000,'Fonds Propres','IDVEY',49100,1,49100),
(212,'Gabon','2025-06-16','2025-10-10','2025-10',2025,-291,'Risk Advisory','Renforcement des capacités en cybersécurité (formation RSSI)','Caisse Nationale de Sécurité Sociale du Gabon','AO','Infructueux',80000,'GIZ',NULL,83600,NULL,NULL),
(213,'Tunisie','2025-09-09','2025-10-08','2025-10',2025,-293,'Risk Advisory','Mise en place d\'un Centre Opérationnel de Sécurité (SOC)','INTT','Consultation','Offre gagnée',250000,'Fonds Propres',NULL,232700,1,232700),
(214,'Bénin','2025-06-18','2025-10-07','2025-10',2025,-294,'Risk Advisory','PCA','Agence Nationale des Transports Terrestres','Prospection','Offre gagnée',1500000,'AFD','Pragma',1432900,1,1432900),
(215,'Sénégal','2025-07-15','2025-10-05','2025-10',2025,-296,'Digital Transformation','Lot 1 : Étude de cadrage et spécifications techniques pour l’extension du système CCSMIS','UNICEF','AO','Offre signée',50000,'GIZ',NULL,52400,1,52400),
(216,'Libéria','2025-07-23','2025-10-04','2025-10',2025,-297,'Digital Transformation','Sélection d\'un intégrateur pour un système de gestion documentaire','Central Bank of liberia','AO','Offre perdue',500000,'Fonds Propres','Keyrus',500400,NULL,NULL),
(217,'France','2025-04-24','2025-10-04','2025-10',2025,-297,'Digital Transformation','Ressource Régie Informatica','Keyrus','DP','Offre perdue',350000,'Fonds Propres',NULL,308800,NULL,NULL),
(218,'Côte d\'Ivoire','2025-06-26','2025-10-04','2025-10',2025,-297,'Data Management','Recruitment of a Consulting Firm to Support Data Governance Framework','BAD','DP','Offre perdue',1500000,'BAD',NULL,1533900,NULL,NULL),
(219,'Sénégal','2025-05-05','2025-10-02','2025-10',2025,-299,'Digital Transformation','Lot 2 : Étude de cadrage et definition des spécifications techniques pour une plateforme de suivi des services Eau, Hygiène et Assainissement, Energie et bâtiments dans les centres de santé de base','UNICEF','AO','Hors scope',750000,'GIZ',NULL,662000,NULL,NULL),
(220,'Burundi','2025-04-23','2025-10-01','2025-10',2025,-300,'Risk Advisory','Assistance technique pour le recrutement d’un Bureau spécialisé dans l’implémentation d’un système de Management de la Sécurité de l’Information (SMSI) à l’Office Burundais des Recettes (OBR)','PAFEN','DP','Offre gagnée',120000,'EU','IDVEY',104100,1,104100),
(221,'Côte d\'Ivoire','2025-05-22','2025-09-30','2025-09',2025,-301,'Risk Advisory','Élaboration de la PSSI','CDC-CI','DP','Offre signée',500000,'Banque Mondiale',NULL,429600,1,429600),
(222,'Tunisie','2025-08-15','2025-09-30','2025-09',2025,-301,'Digital Transformation','Etude d\'urbanisation du Système d\'Information','Paulina','DP','NO GO',50000,'Fonds Propres','FTHM',47900,NULL,NULL),
(223,'Tunisie','2025-04-29','2025-09-19','2025-09',2025,-312,'Risk Advisory','Renforcement des capacités en cybersécurité (formation RSSI)','ITCEQ','DP','Offre gagnée',120000,'Fonds Propres','Medianet',120300,1,120300),
(224,'Tunisie','2025-07-24','2025-09-03','2025-09',2025,-328,'Risk Advisory','Mise en place d\'un Centre Opérationnel de Sécurité (SOC)','SNCFT','DP','Offre perdue',250000,'UNDP','Expertise Advisors',256800,NULL,NULL),
(225,'Tunisie','2025-05-31','2025-09-01','2025-09',2025,-330,'Digital Transformation','AMOA Choix ERP pour les IMF Régionales','Banque Tunisienne de Solidarité (BTS)','DP','Infructueux',500000,'Fonds Propres',NULL,462900,NULL,NULL),
(226,'Togo','2025-07-27','2025-08-27','2025-08',2025,-335,'Digital Transformation','Etude de cadrage pour la mise en place d\'un ERP','Ministère des Finances du Togo','Consultation','Non shortlisté',350000,'ENABEL','Medianet',340100,NULL,NULL),
(227,'Comores','2025-04-10','2025-08-24','2025-08',2025,-338,'Risk Advisory','Recrutement d\'un cabinet pour l\'audit organisationnel de la DSI','Banque Postale Comores','Gré à gré','Non shortlisté',80000,'Fonds Propres','ADDINN',78200,NULL,NULL),
(228,'Arabie Saoudite','2025-07-07','2025-08-20','2025-08',2025,-342,'Digital Transformation','One ISO 9001 resource. One ressource AFQM','Dvt KSA','Gré à gré','Offre gagnée',80000,'Fonds Propres','Hedal Consulting',78100,1,78100),
(229,'Tunisie','2025-04-20','2025-08-17','2025-08',2025,-345,'Risk Advisory','Mission Gouvernance des Données (prévoir une réunion avec DSI et RSSI (qui est aussi le responsable de la partie Data))','Al Baraka','DP','Offre perdue',120000,'Fonds Propres','DWT',122000,NULL,NULL),
(230,'Tchad','2025-05-31','2025-08-17','2025-08',2025,-345,'Risk Advisory','Recrutement d\'un cabinet pour l\'audit organisationnel de la DSI','Projet d\'Appui à la Decentralisation et au Développement des Villes','AO','Offre signée',120000,'AFD','FTHM',104300,1,104300),
(231,'Mauritanie','2025-04-24','2025-08-15','2025-08',2025,-347,'Risk Advisory','Audit Sécurité','Mattel','DP','Hors scope',1000000,'Fonds Propres',NULL,914600,NULL,NULL),
(232,'Gabon','2025-07-09','2025-08-13','2025-08',2025,-349,'Digital Transformation','Assistance à Maîtrise d\'Ouvrage (AMOA) pour la refonte du SI','Petro Gabon','AMI','Offre signée',750000,'Fonds Propres',NULL,727100,1,727100),
(233,'Tunisie','2025-07-04','2025-08-10','2025-08',2025,-352,'Digital Transformation','AMOA ERP','ANCE','Prospection','Infructueux',80000,'ENABEL',NULL,70700,NULL,NULL),
(234,'Tunisie','2025-06-23','2025-08-09','2025-08',2025,-353,'Data Management','Uses Cases IA','Banque Zitouna','AO','Offre gagnée',1000000,'Fonds Propres',NULL,993100,1,993100),
(235,'Bénin','2025-05-13','2025-08-08','2025-08',2025,-354,'Risk Advisory','Audit de sécurité du Système d\'Information','DGI','DP','Offre gagnée',750000,'EU','Medianet',669300,1,669300),
(236,'Arabie Saoudite','2025-02-26','2025-08-07','2025-08',2025,-355,'Digital Transformation','Consultant Expert Capital Market','Dvt KSA','Consultation','Non shortlisté',500000,'Fonds Propres',NULL,493600,NULL,NULL),
(237,'Tunisie','2025-04-08','2025-08-03','2025-08',2025,-359,'Digital Transformation','Accompagnement au changement pour le déploiement d\'un nouvel ERP','TunisRe','DP','Offre gagnée',50000,'Fonds Propres','ADDINN',52200,1,52200),
(238,'Côte d\'Ivoire','2025-05-30','2025-07-31','2025-07',2025,-362,'Data Management','Mise en place d\'un tableau de bord de pilotage (Business Intelligence)','UNACOOPEC-CI','Consultation','Offre perdue',250000,'Banque Mondiale','Finetech',230400,NULL,NULL),
(239,'Maroc','2025-06-13','2025-07-31','2025-07',2025,-362,'Risk Advisory','Elaboration du Plan de Continuité d\'Activité (PCA)','BMCI','AMI','Hors scope',80000,'Fonds Propres','Expertise Advisors',69300,NULL,NULL),
(240,'Tunisie','2025-06-13','2025-07-27','2025-07',2025,-366,'Risk Advisory','Audit sauvegarde replication','Al Baraka','DP','NO GO',1500000,'Fonds Propres',NULL,1411600,NULL,NULL),
(241,'Bénin','2025-06-02','2025-07-26','2025-07',2025,-367,'Digital Transformation','Etudes préalables à l’implémentation et l’élaboration des termes de référence et des cahiers de charges pour la mise en œuvre du sous-projet « digitalisation du conseil des ministres »','PATN','Prospection','Infructueux',80000,'Kfw','Finetech',78600,NULL,NULL),
(242,'Tunisie','2025-06-12','2025-07-25','2025-07',2025,-368,'Risk Advisory','Mise en place d\'une Politique de Sécurité des Systèmes d\'Information (PSSI)','Enda TAO','AO','Hors scope',180000,'Fonds Propres',NULL,167300,NULL,NULL),
(243,'Côte d\'Ivoire','2025-06-15','2025-07-24','2025-07',2025,-369,'Risk Advisory','Mise en conformité avec la réglementation sur la protection des données','Petro Ivoire','AMI','Non shortlisté',80000,'Fonds Propres','Medianet',80400,NULL,NULL),
(244,'Bénin','2025-02-16','2025-07-23','2025-07',2025,-370,'Digital Transformation','Elaboration du Schéma Directeur des Systèmes d\'Information','Agence de Développement de Sèmè City','AMI','Offre perdue',500000,'AFD',NULL,485200,NULL,NULL),
(245,'Togo','2025-06-06','2025-07-23','2025-07',2025,-370,'Risk Advisory','Mise en place d\'une Politique de Sécurité des Systèmes d\'Information (PSSI)','Ministère des Finances du Togo','AMI','Offre gagnée',750000,'Suisse','Medianet',692000,1,692000),
(246,'Bénin','2025-05-14','2025-07-23','2025-07',2025,-370,'Risk Advisory','Assistance à l\'inspection des projets (Gouvernance, Dispositif de Contrôle Interne et Gestion des Risques)','CDC Bénin','Consultation','Offre perdue',750000,'Banque Mondiale','FTHM',775400,NULL,NULL),
(247,'Mauritanie','2025-04-06','2025-07-16','2025-07',2025,-377,'Digital Transformation','Accompagnement au changement pour le déploiement d\'un nouvel ERP','Mattel','DP','Offre signée',350000,'Fonds Propres',NULL,337300,1,337300),
(248,'Bénin','2025-03-26','2025-07-13','2025-07',2025,-380,'Risk Advisory','Recrutement d\'un consultant pour la définition et la vulgarisation d\'un cadre d\'analyse des risques (objectif EBIOS)','ASIN','AMI','Offre gagnée',500000,'ENABEL',NULL,478700,1,478700),
(249,'Guinée','2025-01-22','2025-07-10','2025-07',2025,-383,'Digital Transformation','Etude de l Interconnexion entre la Douanes de Guinée et Guinée Bissau','AGEROUTE','AO','Offre perdue',1000000,'AFD',NULL,982700,NULL,NULL),
(250,'Tunisie','2025-01-26','2025-06-30','2025-06',2025,-393,'Risk Advisory','Renforcement des capacités en cybersécurité (formation RSSI)','ANCE','DP','Offre gagnée',180000,'BAD',NULL,182900,1,182900),
(251,'Cameroun','2025-03-13','2025-06-29','2025-06',2025,-394,'Digital Transformation','Accompagnement au changement pour le déploiement d\'un nouvel ERP','Banque des Etats de l\'Afrique Centrale (BEAC)','Consultation','Offre gagnée',1500000,'GIZ','GT Consulting',1513500,1,1513500),
(252,'Tunisie','2025-01-26','2025-06-29','2025-06',2025,-394,'Digital Transformation','Assistance à Maîtrise d\'Ouvrage (AMOA) pour la refonte du SI','SNCFT','AO','Offre gagnée',1500000,'GIZ','GT Consulting',1409100,1,1409100),
(253,'Bénin','2025-05-31','2025-06-28','2025-06',2025,-395,'Risk Advisory','Recrutement d\'un consultant pour l\'élaboration des outils de contrôle interne et de mitigation des risques (cartographie des risques, manuels de procédures, guides d\'audit, etc.) au profit du Secrétariat Général du Ministère des Finances','Projet de Gouvernement Économique et de Délivrance des Services au Bénin (PGEDS)','DP','Offre gagnée',1000000,'AFD','Expertise Advisors',982800,1,982800),
(254,'Tunisie','2025-02-10','2025-06-27','2025-06',2025,-396,'Risk Advisory','Mise en place d\'un Centre Opérationnel de Sécurité (SOC)','OMMP','Consultation','Offre perdue',750000,'EU','Pragma',698200,NULL,NULL),
(255,'Bénin','2025-04-14','2025-06-25','2025-06',2025,-398,'Digital Transformation','Appui à la mise en place d\'interfaces avec eQuittance et Tresorpay et Appui au développement complémentaire de modules et fonctionnalités de l\'application guichet unique','ASIN','DP','Offre perdue',350000,'AFD','DWT',304900,NULL,NULL),
(256,'Tunisie','2025-05-03','2025-06-20','2025-06',2025,-403,'Risk Advisory','PCA','Enda TAO','AO','Offre signée',500000,'Fonds Propres','Pragma',516500,1,516500),
(257,'Bénin','2025-03-14','2025-06-20','2025-06',2025,-403,'Digital Transformation','Elaboration du Schéma Directeur des Systèmes d\'Information','Société des Aéroports du Bénin','Consultation','Non shortlisté',180000,'GIZ',NULL,182100,NULL,NULL),
(258,'Tunisie','2025-02-17','2025-06-18','2025-06',2025,-405,'Digital Transformation','élaboration d\'un schéma directeur informatique (SDI)','CNSS','AO','Offre gagnée',180000,'GIZ','IDVEY',173600,1,173600),
(259,'Togo','2025-03-05','2025-06-16','2025-06',2025,-407,'Risk Advisory','Audit de sécurité du Système d\'Information','Ecobank Togo','DP','Offre perdue',180000,'AFD',NULL,186700,NULL,NULL),
(260,'Mauritanie','2025-04-17','2025-06-13','2025-06',2025,-410,'Data Management','Mise en place d\'un tableau de bord de pilotage (Business Intelligence)','WARDIP','AMI','NO GO',180000,'AFD',NULL,161800,NULL,NULL),
(261,'Bénin','2025-03-01','2025-06-10','2025-06',2025,-413,'Risk Advisory','Mise en oeuvre PCA','Office du Commerce','AO','Offre gagnée',750000,'ENABEL','Expertise Advisors',644400,1,644400),
(262,'Tunisie','2025-03-01','2025-06-10','2025-06',2025,-413,'Risk Advisory','Recrutement d\'un cabinet pour l\'audit organisationnel de la DSI','CEPEX','AO','Offre perdue',350000,'UNDP','IMCG',352400,NULL,NULL),
(263,'Gabon','2024-12-23','2025-06-09','2025-06',2025,-414,'Digital Transformation','Assistance à Maîtrise d\'Ouvrage (AMOA) pour la refonte du SI','Caisse Nationale de Sécurité Sociale du Gabon','AO','Infructueux',250000,'Fonds Propres',NULL,232300,NULL,NULL),
(264,'Tunisie','2025-04-14','2025-06-08','2025-06',2025,-415,'Risk Advisory','lot 2 : élaboration d’un plan de continuité d’activité (PCA)','INTT','AO','NO GO',50000,'AFD','IDVEY',47300,NULL,NULL),
(265,'Cameroun','2025-02-03','2025-06-08','2025-06',2025,-415,'Risk Advisory','Plan de Continuité d\'Activité','GIMAC','Avant-vente','Offre perdue',500000,'Fonds Propres',NULL,497600,NULL,NULL),
(266,'Tunisie','2024-12-17','2025-06-04','2025-06',2025,-419,'Risk Advisory','lot 3 : Mise en place d’une politique de sécurité du système d’information (PSSI)','INTT','AO','Offre gagnée',1500000,'GIZ',NULL,1500700,1,1500700),
(267,'Tunisie','2024-12-14','2025-05-30','2025-05',2025,-424,'Risk Advisory','Actualisation & Maintien du PCA (Horizon sur 03 ans)','Al Baraka','AO','NO GO',1000000,'Fonds Propres',NULL,860300,NULL,NULL),
(268,'Côte d\'Ivoire','2025-03-12','2025-05-29','2025-05',2025,-425,'Digital Transformation','Accompagnement à la Transformation Digitale','GESTOCI','DP','Offre perdue',120000,'BAD',NULL,117900,NULL,NULL),
(269,'Bénin','2025-04-03','2025-05-28','2025-05',2025,-426,'Digital Transformation','Mise en place du Plan de Reprise d\'Activités','Société des Aéroports du Bénin','AO','Non shortlisté',50000,'BAD',NULL,49400,NULL,NULL),
(270,'Mauritanie','2024-12-17','2025-05-23','2025-05',2025,-431,'Digital Transformation','Accompagnement à la Transformation Digitale','Mauritania Airlines','AMI','Offre gagnée',350000,'Fonds Propres','IDVEY',340500,1,340500),
(271,'Bénin','2025-03-20','2025-05-22','2025-05',2025,-432,'Risk Advisory','Recrutement d\'un prestataire pour la formation de vingt (20) Responsable de la Sécurité des Systèmes d\'Information (RSSI) de l\'administration','ASIN','AO','Non shortlisté',80000,'BAD',NULL,73400,NULL,NULL),
(272,'Bénin','2024-12-20','2025-05-20','2025-05',2025,-434,'Risk Advisory','Acquisition et mise en œuvre des actions de cyber sécurité pour la mise en conformité à la Politique de Sécurité des Systèmes d\'Information de l\'Etat (PSSIE) et la Politique de Protection des Infrastructures d\'Information Critique (PPIC) dans le cadre du projet DEFISSOL (procédure reconduite)','SBEE','DP','Offre signée',80000,'Fonds Propres',NULL,70500,1,70500),
(273,'Tunisie','2025-03-03','2025-05-18','2025-05',2025,-436,'Risk Advisory','Mise en place d\'une Politique de Sécurité des Systèmes d\'Information (PSSI)','Carrefour - UHD','AMI','Offre perdue',120000,'Fonds Propres',NULL,113900,NULL,NULL),
(274,'Tunisie','2025-03-26','2025-05-17','2025-05',2025,-437,'Digital Transformation','Testing factory ( Régie ) / Renforcement capacité DSI ( AMOA / PMO )','BTK','DP','Offre perdue',750000,'Fonds Propres',NULL,768100,NULL,NULL),
(275,'Côte d\'Ivoire','2025-04-14','2025-05-14','2025-05',2025,-440,'Risk Advisory','Audit de sécurité du Système d\'Information','SODECI','DP','Hors scope',750000,'UNDP','ADDINN',655800,NULL,NULL),
(276,'Tunisie','2025-02-21','2025-05-12','2025-05',2025,-442,'Risk Advisory','Recrutement d\'un consultant pour la cartographie des risques IT','API','AMI','Offre perdue',1000000,'ENABEL',NULL,926700,NULL,NULL),
(277,'Côte d\'Ivoire','2024-12-10','2025-05-12','2025-05',2025,-442,'Digital Transformation','Assistance à Maîtrise d\'Ouvrage (AMOA) pour la refonte du SI','CIE Côte d\'Ivoire','Consultation','Offre gagnée',120000,'EU','Pragma',112700,1,112700),
(278,'Tunisie','2025-01-07','2025-05-12','2025-05',2025,-442,'Risk Advisory','Mise en conformité avec la réglementation sur la protection des données','Ecole Nationale des Finances','AO','Non shortlisté',50000,'Banque Mondiale',NULL,49500,NULL,NULL),
(279,'Tunisie','2025-03-28','2025-05-11','2025-05',2025,-443,'Risk Advisory','PCA','TunisRe','Consultation','Non shortlisté',750000,'Fonds Propres',NULL,738400,NULL,NULL),
(280,'Bénin','2024-12-04','2025-05-11','2025-05',2025,-443,'Digital Transformation','Recrutement d\'un prestataire pour étude et mise en place d\'un plan de développement et d\'intégration des applications d\'Etat','ASIN','Consultation','Offre gagnée',180000,'Banque Mondiale','ADDINN',153400,1,153400),
(281,'Bénin','2024-12-08','2025-05-09','2025-05',2025,-445,'Risk Advisory','Réalisation et publication d\'une étude sur l\'état des cyber-menaces au Bénin','ASIN','Consultation','Offre signée',500000,'AFD','Finetech',488600,1,488600),
(282,'Bénin','2025-04-03','2025-05-07','2025-05',2025,-447,'Digital Transformation','Etude de faisabilité pour la migration vers le Cloud','Port Autonome de Cotonou','DP','Offre gagnée',350000,'AFD',NULL,313700,1,313700),
(283,'Sénégal','2025-02-02','2025-05-06','2025-05',2025,-448,'Risk Advisory','Renforcement des capacités en cybersécurité (formation RSSI)','SONATEL','Gré à gré','Offre perdue',1000000,'Kfw',NULL,941100,NULL,NULL),
(284,'Bénin','2025-02-24','2025-05-04','2025-05',2025,-450,'Digital Transformation','Assistance à Maîtrise d\'Ouvrage (AMOA) pour la refonte du SI','Agence Nationale des Transports Terrestres','DP','Infructueux',500000,'EU',NULL,490900,NULL,NULL),
(285,'Mali','2024-12-21','2025-05-03','2025-05',2025,-451,'Risk Advisory','Elaboration du Plan de Continuité d\'Activité (PCA)','Mansa Bank','AO','Offre perdue',120000,'Fonds Propres','DWT',104700,NULL,NULL),
(286,'Tunisie','2024-12-03','2025-04-30','2025-04',2025,-454,'Digital Transformation','AMOA Choix ERP pour les IMF Régionales','Banque Tunisienne de Solidarité (BTS)','AMI','Non shortlisté',500000,'Fonds Propres',NULL,516600,NULL,NULL),
(287,'Tunisie','2024-12-06','2025-04-28','2025-04',2025,-456,'Data Management','Placement régie 2 ETP Data','Attijari Bank','Consultation','Non shortlisté',80000,'Fonds Propres',NULL,76500,NULL,NULL),
(288,'Bénin','2025-03-17','2025-04-25','2025-04',2025,-459,'Digital Transformation','Etude de faisabilité pour la migration vers le Cloud','Port Autonome de Cotonou','AMI','NO GO',350000,'AFD',NULL,357400,NULL,NULL),
(289,'Bénin','2025-03-21','2025-04-23','2025-04',2025,-461,'Risk Advisory','Élaboration du document de politique de sécurité des systèmes d\'informations de la SBIR','Société Béninoise de Radio Diffusion','AMI','Offre perdue',250000,'Banque Mondiale',NULL,261400,NULL,NULL),
(290,'Tunisie','2024-12-13','2025-04-21','2025-04',2025,-463,'Risk Advisory','Recrutement d\'un consultant pour la cartographie des risques IT','STEG','AMI','Offre gagnée',50000,'ENABEL','ADDINN',47000,1,47000),
(291,'Mauritanie','2024-10-24','2025-04-20','2025-04',2025,-464,'Digital Transformation','Etude d\'urbanisation du Système d\'Information','Agence du Développement Economique Urbain','Avant-vente','Offre gagnée',180000,'Banque Mondiale',NULL,163300,1,163300),
(292,'Bénin','2025-02-03','2025-04-19','2025-04',2025,-465,'Risk Advisory','Elaboration d\'un modèle de référence pour la cyber-résilience et pour la mise en place de Plan de Continuité d\'Activité pour les entreprises opérant des infrastructures d\'information critiques','ASIN','DP','Offre gagnée',250000,'ENABEL',NULL,230200,1,230200),
(293,'Bénin','2025-01-22','2025-04-17','2025-04',2025,-467,'Digital Transformation','Sélection d\'un cabinet ou d\'un bureau d\'études pour le renforcement de la structure organisationnelle et de gestion des ressources humaines','Mairie de Cotonou','AO','Offre gagnée',50000,'Banque Mondiale',NULL,43800,1,43800),
(294,'Tunisie','2025-02-10','2025-04-14','2025-04',2025,-470,'Risk Advisory','Plan de Continuité Informatique et du Plan de Reprise Informatique','CNSS','AO','Offre signée',180000,'BEI',NULL,181800,1,181800),
(295,'Tunisie','2025-02-12','2025-04-13','2025-04',2025,-471,'Digital Transformation','Assistance Technique pour l\'Elaboration d\'un Cahier des Charges pour la conception d\'un SI pédagogique intégré','Ecole Nationale des Finances','Prospection','NO GO',1000000,'GIZ','ADDINN',864800,NULL,NULL),
(296,'Tunisie','2024-10-26','2025-04-06','2025-04',2025,-478,'Digital Transformation','Elaboration SDSI','CNSS','Avant-vente','Offre perdue',350000,'AFD',NULL,359600,NULL,NULL),
(297,'Burkina Faso','2024-10-08','2025-04-05','2025-04',2025,-479,'Risk Advisory','Mise en conformité avec la réglementation sur la protection des données','SONABEL','DP','Infructueux',1000000,'Fonds Propres',NULL,891200,NULL,NULL),
(298,'Tunisie','2025-01-24','2025-04-03','2025-04',2025,-481,'Digital Transformation','STB, referencement','STB','AO','NO GO',50000,'Fonds Propres',NULL,52500,NULL,NULL),
(299,'Libéria','2024-11-12','2025-03-26','2025-03',2025,-489,'Digital Transformation','RFI : InterBank payment and settlement system','Central Bank of liberia','DP','Offre perdue',250000,'Fonds Propres','Pragma',230500,NULL,NULL),
(300,'Bénin','2025-01-31','2025-03-26','2025-03',2025,-489,'Digital Transformation','Etude de cadrage pour la mise en place d\'un ERP','Ministère des environnements','AMI','Offre gagnée',120000,'Fonds Propres',NULL,111500,1,111500),
(301,'Côte d\'Ivoire','2024-12-24','2025-03-25','2025-03',2025,-490,'Digital Transformation','Accompagnement à la Transformation Digitale','GESTOCI','AMI','Offre perdue',120000,'BAD',NULL,120900,NULL,NULL),
(302,'Mauritanie','2024-12-06','2025-03-25','2025-03',2025,-490,'Digital Transformation','Accompagnement au changement pour le déploiement d\'un nouvel ERP','Mattel','AMI','Offre gagnée',350000,'Fonds Propres',NULL,315000,1,315000),
(303,'Cameroun','2024-10-29','2025-03-22','2025-03',2025,-493,'Digital Transformation','Etude de cadrage pour la mise en place d\'un ERP','GIMAC','AMI','Offre gagnée',180000,'Fonds Propres',NULL,171300,1,171300),
(304,'Mauritanie','2024-11-26','2025-03-22','2025-03',2025,-493,'Digital Transformation','Assistance à Maîtrise d\'Ouvrage (AMOA) pour la refonte du SI','SOMELEC','DP','Offre gagnée',50000,'Fonds Propres',NULL,45600,1,45600),
(305,'Cameroun','2024-10-24','2025-03-20','2025-03',2025,-495,'Risk Advisory','Mise en oeuvre PCA','Société Sucrière du Cameroun','Consultation','Offre signée',750000,'Fonds Propres','Keyrus',657100,1,657100),
(306,'Gabon','2024-10-22','2025-03-18','2025-03',2025,-497,'Data Management','Mission d\'assistance technique pour la gouvernance des données','Caisse Nationale de Sécurité Sociale du Gabon','AO','Offre perdue',750000,'Banque Mondiale','Expertise Advisors',717800,NULL,NULL),
(307,'Mauritanie','2025-01-08','2025-03-17','2025-03',2025,-498,'Risk Advisory','Audit Sécurité','Mattel','AMI','NO GO',1000000,'Fonds Propres',NULL,928000,NULL,NULL),
(308,'Bénin','2024-09-27','2025-03-12','2025-03',2025,-503,'Risk Advisory','Mise en place d\'une Politique de Sécurité des Systèmes d\'Information (PSSI)','Société Béninoise de Radio Diffusion','DP','Offre gagnée',180000,'Fonds Propres',NULL,176300,1,176300),
(309,'Tunisie','2024-11-20','2025-03-12','2025-03',2025,-503,'Data Management','Mission d\'assistance technique pour la gouvernance des données','BTK','Avant-vente','Offre perdue',500000,'Fonds Propres','IMCG',516500,NULL,NULL),
(310,'Bénin','2024-09-24','2025-03-11','2025-03',2025,-504,'Risk Advisory','Audit de sécurité du Système d\'Information','Agence Nationale des Transports Terrestres','DP','Offre perdue',500000,'AFD',NULL,432800,NULL,NULL),
(311,'Comores','2025-01-05','2025-03-10','2025-03',2025,-505,'Digital Transformation','Organisation DSI','Banque Postale Comores','AO','Offre gagnée',750000,'Fonds Propres',NULL,720300,1,720300),
(312,'Côte d\'Ivoire','2025-01-15','2025-03-08','2025-03',2025,-507,'Digital Transformation','Etude d\'urbanisation du Système d\'Information','CIE Côte d\'Ivoire','DP','Offre perdue',350000,'Fonds Propres',NULL,329900,NULL,NULL),
(313,'Bénin','2025-01-02','2025-03-07','2025-03',2025,-508,'Risk Advisory','recrutrement d\'un prestataire pour la finalisation de l\'Implémentation du Système de Management de Sécurité de l\'Information (SMSI) : ISO 27001','Société des Aéroports du Bénin','AO','NO GO',500000,'Fonds Propres','Medianet',469400,NULL,NULL),
(314,'Burkina Faso','2024-10-26','2025-03-06','2025-03',2025,-509,'Digital Transformation','Schéma Directeur des SI','SONABEL','Gré à gré','Offre perdue',1000000,'Fonds Propres','Pragma',856800,NULL,NULL),
(315,'Cameroun','2024-10-02','2025-03-06','2025-03',2025,-509,'Digital Transformation','Etude de cadrage pour la mise en place d\'un ERP','Société Sucrière du Cameroun','DP','Infructueux',180000,'Fonds Propres','IMCG',175100,NULL,NULL),
(316,'Arabie Saoudite','2024-09-12','2025-03-04','2025-03',2025,-511,'Digital Transformation','2 profiles for DevSecOps Engineers','Dvt KSA','Consultation','Infructueux',500000,'Fonds Propres','Hedal Consulting',456700,NULL,NULL),
(317,'Tunisie','2024-10-13','2025-03-04','2025-03',2025,-511,'Digital Transformation','Etude d\'urbanisation du Système d\'Information','SNCFT','DP','Infructueux',250000,'GIZ','IDVEY',239400,NULL,NULL),
(318,'Bénin','2024-09-29','2025-03-03','2025-03',2025,-512,'Digital Transformation','Assistance à Maîtrise d\'Ouvrage (AMOA) pour la refonte du SI','CDC Bénin','AO','Offre perdue',1000000,'ENABEL','Pragma',1015800,NULL,NULL),
(319,'Bénin','2024-10-12','2025-02-24','2025-02',2025,-519,'Digital Transformation','SDSI','Ministère du tourisme','DP','Offre perdue',1000000,'Suisse',NULL,920200,NULL,NULL),
(320,'Tchad','2024-11-04','2025-02-21','2025-02',2025,-522,'Digital Transformation','Etude de faisabilité pour la migration vers le Cloud','Projet d\'Appui à la Decentralisation et au Développement des Villes','AO','Offre signée',350000,'AFD','ADDINN',334000,1,334000),
(321,'Bénin','2024-10-19','2025-02-19','2025-02',2025,-524,'Risk Advisory','Audit de sécurité du Système d\'Information','DGI','Gré à gré','Non shortlisté',350000,'BAD','Keyrus',339600,NULL,NULL),
(322,'Mali','2024-08-28','2025-02-17','2025-02',2025,-526,'Risk Advisory','PCA','GIMTEL','AO','Offre gagnée',1000000,'Fonds Propres',NULL,962800,1,962800),
(323,'Tunisie','2024-11-20','2025-02-16','2025-02',2025,-527,'Digital Transformation','AMOA SAP','STEG','DP','Offre gagnée',500000,'EU','ADDINN',455300,1,455300),
(324,'Tunisie','2024-10-07','2025-02-15','2025-02',2025,-528,'Digital Transformation','Accompagnement à la Transformation Digitale','Ecole Nationale des Finances','DP','Offre signée',500000,'AFD',NULL,479100,1,479100),
(325,'Bénin','2024-11-18','2025-02-13','2025-02',2025,-530,'Digital Transformation','SDSI','ONEAD','AMI','Offre perdue',50000,'ENABEL',NULL,52200,NULL,NULL),
(326,'Bénin','2024-12-14','2025-02-13','2025-02',2025,-530,'Data Management','Stratégie nationale de gouvernance des données','PATN','DP','Non shortlisté',1000000,'UNDP',NULL,1002200,NULL,NULL),
(327,'Tunisie','2024-12-13','2025-02-09','2025-02',2025,-534,'Data Management','Mission de Data Governance et cartographie des données','OMMP','Avant-vente','Non shortlisté',80000,'EU',NULL,80700,NULL,NULL),
(328,'Tchad','2024-11-22','2025-02-03','2025-02',2025,-540,'Digital Transformation','Etude sur l\'intéropérabilité des Systèmes SIGEL, KALHEL et MOUHASSIL','Projet d\'Appui à la Decentralisation et au Développement des Villes','Avant-vente','Offre gagnée',50000,'UNDP',NULL,52300,1,52300),
(329,'Tunisie','2024-09-23','2025-02-01','2025-02',2025,-542,'Risk Advisory','Recrutement d\'un cabinet pour l\'audit organisationnel de la DSI','STEG','Consultation','Offre perdue',80000,'UNDP','Keyrus',69000,NULL,NULL),
(330,'Bénin','2024-09-18','2025-01-26','2025-01',2025,-548,'Risk Advisory','Audit organisationnel de la DSI du Ministère de la Santé et structures sous tutelle','ASIN','AO','Offre gagnée',1500000,'BEI','FTHM',1344400,1,1344400),
(331,'Tunisie','2024-11-26','2025-01-24','2025-01',2025,-550,'Digital Transformation','Etude de cadrage pour la mise en place d\'un ERP','Zitouna Banque','AMI','Offre perdue',250000,'Fonds Propres',NULL,247100,NULL,NULL),
(332,'Tunisie','2024-11-20','2025-01-24','2025-01',2025,-550,'Risk Advisory','Mise en conformité avec la réglementation sur la protection des données','Paulina','Gré à gré','Non shortlisté',250000,'Fonds Propres','ADDINN',220800,NULL,NULL),
(333,'Côte d\'Ivoire','2024-09-14','2025-01-19','2025-01',2025,-555,'Risk Advisory','Élaboration de la PSSI','CDC-CI','AMI','NO GO',500000,'Banque Mondiale',NULL,491200,NULL,NULL),
(334,'Bénin','2024-12-03','2025-01-18','2025-01',2025,-556,'Digital Transformation','Assistance à Maîtrise d\'Ouvrage (AMOA) pour la refonte du SI','SBEE','AO','Offre perdue',80000,'GIZ',NULL,80700,NULL,NULL),
(335,'Côte d\'Ivoire','2024-12-08','2025-01-16','2025-01',2025,-558,'Data Management','Recruitment of a Consulting Firm to Support Data Governance Framework','BAD','AMI','Infructueux',1500000,'BAD',NULL,1320800,NULL,NULL),
(336,'Bénin','2024-08-07','2025-01-15','2025-01',2025,-559,'Risk Advisory','Renforcement des capacités en cybersécurité (formation RSSI)','ANADEC','AO','Offre gagnée',250000,'Kfw',NULL,214200,1,214200),
(337,'Tunisie','2024-09-13','2025-01-15','2025-01',2025,-559,'Digital Transformation','Sélection d\'un intégrateur pour un système de gestion documentaire','STEG','AO','Offre perdue',250000,'ENABEL',NULL,255700,NULL,NULL),
(338,'Mauritanie','2024-07-20','2025-01-13','2025-01',2025,-561,'Data Management','Mise en Place d’une Solution de Business Intelligence (BI) et de Gestion des Données - CSIE','SOMELEC','AO','Non shortlisté',1500000,'Fonds Propres','Medianet',1362500,NULL,NULL),
(339,'Tunisie','2024-10-12','2025-01-07','2025-01',2025,-567,'Digital Transformation','Etude de faisabilité pour la migration vers le Cloud','Office du Commerce','AMI','Offre perdue',350000,'EU',NULL,365800,NULL,NULL),
(340,'Tunisie','2024-09-03','2025-01-07','2025-01',2025,-567,'Risk Advisory','PCA','Carrefour - UHD','Prospection','NO GO',750000,'Fonds Propres',NULL,762700,NULL,NULL),
(341,'Tunisie','2026-06-10','2026-07-20','2026-07',2026,-8,'Data Management','Mise en place d’un tableau de bord de pilotage commercial','BIAT','AO','DP',300000,'Fonds Propres','FTHM',285000,0.6,171000),
(342,'Tunisie','2026-06-20','2026-07-30','2026-07',2026,2,'Digital Transformation','Accompagnement à la transformation digitale des processus RH','STEG','AMI','En cours de qualification',420000,'Fonds Propres',NULL,410000,0.5,205000),
(343,'Bénin','2026-05-01','2026-08-29','2026-08',2026,32,'Risk Advisory','Audit de sécurité des systèmes d’information','ENABEL','Prospection','Lead',180000,'ENABEL',NULL,175000,0.3,52500),
(344,'Maroc','2026-05-11','2026-07-26','2026-07',2026,-2,'Digital Transformation','Mise en place d’un système de gestion de la relation client (CRM)','Enda TAO','AMI','AMI',300000,'EU','FTHM',287096,0.3,86128.8),
(345,'Gabon','2026-05-19','2026-07-16','2026-07',2026,-12,'Digital Transformation','Elaboration d’un schéma directeur informatique','SONABEL','AMI','Manif shortlistée',120000,'BAD','FTHM',109418,0.6,65650.8),
(346,'Gabon','2026-05-19','2026-08-12','2026-08',2026,15,'Risk Advisory','Audit organisationnel et cartographie des processus','SONABEL','AMI','Complément d\'information',300000,'Fonds Propres','FTHM',280255,0.8,224204),
(347,'Tunisie','2026-05-22','2026-10-08','2026-10',2026,72,'Data Management','Déploiement d’une solution de Business Intelligence','STEG','AMI','En cours de qualification',600000,'EU','Medianet',571974,0.5,285987),
(348,'Maroc','2026-05-28','2026-07-17','2026-07',2026,-11,'Risk Advisory','Etude de faisabilité pour la migration Cloud','STEG','Prospection','Lead',250000,'ENABEL','Medianet',239229,0.6,143537.4),
(349,'Maroc','2026-05-16','2026-08-14','2026-08',2026,17,'Digital Transformation','Accompagnement à la certification ISO 27001','BIAT','AO','Manif shortlistée',120000,'EU','Talan',109191,0.5,54595.5),
(350,'Bénin','2026-04-18','2026-07-15','2026-07',2026,-13,'Risk Advisory','Mise en place d’un entrepôt de données (Data Warehouse)','CORIS BANK','AMI','Lead',600000,'ENABEL',NULL,562196,0.4,224878.4),
(351,'Mauritanie','2026-06-14','2026-07-29','2026-07',2026,1,'Risk Advisory','Digitalisation du parcours client','SONABEL','AMI','Complément d\'information',500000,'EU','Medianet',488214,0.4,195285.6),
(352,'Gabon','2026-04-27','2026-08-26','2026-08',2026,29,'Data Management','Audit de sécurité des systèmes d’information','STEG','AO','Lead',250000,'BAD','FTHM',239310,0.6,143586),
(353,'Sénégal','2026-06-05','2026-10-23','2026-10',2026,87,'Digital Transformation','Assistance à maîtrise d’ouvrage pour un ERP','SODECI','AO','Lead',180000,'EU',NULL,169924,0.3,50977.2),
(354,'Côte dIvoire','2026-05-31','2026-08-19','2026-08',2026,22,'Data Management','Conception d’un tableau de bord de pilotage','Petro Gabon','Prospection','Manif shortlistée',250000,'Fonds Propres',NULL,244037,0.8,195229.6),
(355,'Bénin','2026-05-10','2026-07-25','2026-07',2026,-3,'Digital Transformation','Mise en conformité RGPD','ENABEL','Prospection','Manif shortlistée',120000,'EU','Talan',110013,0.3,33003.9),
(356,'Gabon','2026-04-18','2026-08-14','2026-08',2026,17,'Digital Transformation','Stratégie de transformation digitale','CDC-CI','AO','AMI',180000,'Fonds Propres','Talan',188405,0.3,56521.5),
(357,'Gabon','2026-05-31','2026-10-29','2026-10',2026,93,'Data Management','Optimisation des processus achats','ENABEL','Prospection','En attente du plan de charge',250000,'EU','Talan',259834,0.4,103933.6),
(358,'Maroc','2026-06-17','2026-07-20','2026-07',2026,-8,'Digital Transformation','Mise en place d’une gouvernance des données','ASIN','Prospection','Lead',420000,'BAD','Talan',393618,0.3,118085.4),
(359,'Mauritanie','2026-05-27','2026-07-15','2026-07',2026,-13,'Data Management','Assistance technique pour un projet de dématérialisation','SONABEL','Prospection','AMI',300000,'Fonds Propres','FTHM',298399,0.8,238719.2),
(360,'Tunisie','2026-04-26','2026-07-20','2026-07',2026,-8,'Data Management','Audit du système d’information financier','Enda TAO','AO','Complément d\'information',300000,'EU','Talan',294265,0.4,117706);
/*!40000 ALTER TABLE `opportunities` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Temporary table structure for view `v_by_country`
--

DROP TABLE IF EXISTS `v_by_country`;
/*!50001 DROP VIEW IF EXISTS `v_by_country`*/;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8mb4;
/*!50001 CREATE VIEW `v_by_country` AS SELECT
 1 AS `country`,
  1 AS `nb_opportunities`,
  1 AS `total_budget`,
  1 AS `total_offer`,
  1 AS `total_weighted` */;
SET character_set_client = @saved_cs_client;

--
-- Temporary table structure for view `v_by_country_practice`
--

DROP TABLE IF EXISTS `v_by_country_practice`;
/*!50001 DROP VIEW IF EXISTS `v_by_country_practice`*/;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8mb4;
/*!50001 CREATE VIEW `v_by_country_practice` AS SELECT
 1 AS `country`,
  1 AS `practice`,
  1 AS `nb_opportunities`,
  1 AS `total_budget`,
  1 AS `total_weighted` */;
SET character_set_client = @saved_cs_client;

--
-- Temporary table structure for view `v_by_funding_source`
--

DROP TABLE IF EXISTS `v_by_funding_source`;
/*!50001 DROP VIEW IF EXISTS `v_by_funding_source`*/;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8mb4;
/*!50001 CREATE VIEW `v_by_funding_source` AS SELECT
 1 AS `funding_source`,
  1 AS `nb_opportunities`,
  1 AS `total_budget` */;
SET character_set_client = @saved_cs_client;

--
-- Temporary table structure for view `v_by_month`
--

DROP TABLE IF EXISTS `v_by_month`;
/*!50001 DROP VIEW IF EXISTS `v_by_month`*/;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8mb4;
/*!50001 CREATE VIEW `v_by_month` AS SELECT
 1 AS `deadline_month`,
  1 AS `nb_opportunities`,
  1 AS `total_budget`,
  1 AS `total_offer`,
  1 AS `total_weighted` */;
SET character_set_client = @saved_cs_client;

--
-- Temporary table structure for view `v_by_practice`
--

DROP TABLE IF EXISTS `v_by_practice`;
/*!50001 DROP VIEW IF EXISTS `v_by_practice`*/;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8mb4;
/*!50001 CREATE VIEW `v_by_practice` AS SELECT
 1 AS `practice`,
  1 AS `nb_opportunities`,
  1 AS `total_budget`,
  1 AS `total_offer`,
  1 AS `total_weighted` */;
SET character_set_client = @saved_cs_client;

--
-- Temporary table structure for view `v_by_status`
--

DROP TABLE IF EXISTS `v_by_status`;
/*!50001 DROP VIEW IF EXISTS `v_by_status`*/;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8mb4;
/*!50001 CREATE VIEW `v_by_status` AS SELECT
 1 AS `status`,
  1 AS `nb_opportunities`,
  1 AS `total_budget`,
  1 AS `total_offer` */;
SET character_set_client = @saved_cs_client;

--
-- Dumping routines for database 'devoteam_dashboard'
--

--
-- Current Database: `devoteam_dashboard`
--

USE `devoteam_dashboard`;

--
-- Final view structure for view `v_by_country`
--

/*!50001 DROP VIEW IF EXISTS `v_by_country`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_general_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`root`@`localhost` SQL SECURITY DEFINER */
/*!50001 VIEW `v_by_country` AS select `opportunities`.`country` AS `country`,count(0) AS `nb_opportunities`,sum(`opportunities`.`budget`) AS `total_budget`,sum(`opportunities`.`financial_offer`) AS `total_offer`,sum(`opportunities`.`weighted_amount`) AS `total_weighted` from `opportunities` group by `opportunities`.`country` */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;

--
-- Final view structure for view `v_by_country_practice`
--

/*!50001 DROP VIEW IF EXISTS `v_by_country_practice`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_general_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`root`@`localhost` SQL SECURITY DEFINER */
/*!50001 VIEW `v_by_country_practice` AS select `opportunities`.`country` AS `country`,`opportunities`.`practice` AS `practice`,count(0) AS `nb_opportunities`,sum(`opportunities`.`budget`) AS `total_budget`,sum(`opportunities`.`weighted_amount`) AS `total_weighted` from `opportunities` group by `opportunities`.`country`,`opportunities`.`practice` */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;

--
-- Final view structure for view `v_by_funding_source`
--

/*!50001 DROP VIEW IF EXISTS `v_by_funding_source`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_general_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`root`@`localhost` SQL SECURITY DEFINER */
/*!50001 VIEW `v_by_funding_source` AS select `opportunities`.`funding_source` AS `funding_source`,count(0) AS `nb_opportunities`,sum(`opportunities`.`budget`) AS `total_budget` from `opportunities` group by `opportunities`.`funding_source` */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;

--
-- Final view structure for view `v_by_month`
--

/*!50001 DROP VIEW IF EXISTS `v_by_month`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_general_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`root`@`localhost` SQL SECURITY DEFINER */
/*!50001 VIEW `v_by_month` AS select `opportunities`.`deadline_month` AS `deadline_month`,count(0) AS `nb_opportunities`,sum(`opportunities`.`budget`) AS `total_budget`,sum(`opportunities`.`financial_offer`) AS `total_offer`,sum(`opportunities`.`weighted_amount`) AS `total_weighted` from `opportunities` group by `opportunities`.`deadline_month` order by `opportunities`.`deadline_month` */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;

--
-- Final view structure for view `v_by_practice`
--

/*!50001 DROP VIEW IF EXISTS `v_by_practice`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_general_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`root`@`localhost` SQL SECURITY DEFINER */
/*!50001 VIEW `v_by_practice` AS select `opportunities`.`practice` AS `practice`,count(0) AS `nb_opportunities`,sum(`opportunities`.`budget`) AS `total_budget`,sum(`opportunities`.`financial_offer`) AS `total_offer`,sum(`opportunities`.`weighted_amount`) AS `total_weighted` from `opportunities` group by `opportunities`.`practice` */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;

--
-- Final view structure for view `v_by_status`
--

/*!50001 DROP VIEW IF EXISTS `v_by_status`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_general_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`root`@`localhost` SQL SECURITY DEFINER */
/*!50001 VIEW `v_by_status` AS select `opportunities`.`status` AS `status`,count(0) AS `nb_opportunities`,sum(`opportunities`.`budget`) AS `total_budget`,sum(`opportunities`.`financial_offer`) AS `total_offer` from `opportunities` group by `opportunities`.`status` */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-08-05  9:43:13
