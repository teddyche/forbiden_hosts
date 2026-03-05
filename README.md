# forbidden_hosts — Détection PCI DSS hosts de production en hors-production

Scanne automatiquement tous les inventaires **AAP hors-production** et alerte par email les équipes dont un inventaire contient des hosts appartenant au domaine de **production interdit**.

> **Contexte PCI DSS** : la présence d'un host de production dans un inventaire hors-prod constitue une non-conformité — il peut être ciblé par des jobs Ansible non maîtrisés tournant sur l'environnement de test.

---

## Fonctionnement

```
┌───────────────────────────────────────────────────────────────────────┐
│  forbidden_hosts.yml                                                  │
│                                                                       │
│  1. Scan   → GET /organizations/{id}/inventories/ (toutes les orgs)  │
│             GET /inventories/{id}/hosts/          (tous les hosts)   │
│             → hosts dont le nom se termine par forbidden_host_domain  │
│                                                                       │
│  2. Debug  → synthèse console (N orgs en violation)                  │
│                                                                       │
│  3. Email  → 1 email par org en violation                            │
│              to  : contact_email de l'org                            │
│              cc  : équipe supervision APPOPS                         │
└───────────────────────────────────────────────────────────────────────┘
```

Les emails ne sont envoyés **que si des violations sont détectées**. Une org propre ne reçoit rien.

---

## Structure du projet

```
forbidden_hosts/
├── forbidden_hosts.yml               # Playbook unique : scan + alertes
│
├── filter_plugins/
│   └── inventories.py               # Filtre get_forbidden_hosts
│
├── templates/
│   └── email_forbidden.j2           # Template email Outlook-compatible
│
├── group_vars/
│   └── all.yml                      # Org map, domaine interdit, SMTP, CC
│
└── inventories/
    └── pre/                         # Environnement Hors-Production
        ├── hosts
        └── group_vars/
            ├── all.yml              # env_name, aap_host, aap_token
            └── vault.yml            # vault_aap_token (à chiffrer)
```

---

## Configuration

### Domaine de production interdit (`group_vars/all.yml`)

```yaml
forbidden_host_domain: "not.allow"
```

Tout host dont le nom se **termine** par ce domaine est considéré interdit dans un inventaire hors-prod. Modifier uniquement si le domaine de production change.

Exemples de matching :

| Hostname                 | Résultat |
|--------------------------|----------|
| `myserver.sec-prod1.lan` | Interdit |
| `sec-prod1.lan`          | Interdit |
| `mysec-prod1.lan`        | Autorisé (préfixe sans point) |
| `myserver.sec-prod2.lan` | Autorisé (domaine différent) |

### Organisations (`group_vars/all.yml`)

```yaml
aap_organization_map:
  - id: 8
    name:          "ORG_CAGIP_CAPS_EXM_BOD"
    label:         "EXM BOD"
    contact_email: "equipe-exm-bod@exemple.fr"   # destinataire principal
```

Chaque organisation a un `contact_email` qui reçoit l'alerte si une violation est détectée.

### Emails de supervision (`group_vars/all.yml`)

```yaml
email_cc:
  - "supervision@exemple.fr"
  - "appops@exemple.fr"
```

Ces adresses sont **toujours en copie** de chaque email d'alerte.

### Inventaire (`inventories/pre/group_vars/all.yml`)

```yaml
env_name: "HORS-PRODUCTION 3PG"
aap_host:  "https://votre-aap.exemple.fr"
aap_token: "{{ vault_aap_token }}"
```

---

## Prérequis

```bash
# Ansible
ansible-galaxy collection install community.general

# Python
pip install requests
```

---

## Exécution

### En local (test)

```bash
# Renseigner le token dans le vault, puis :
ansible-vault encrypt inventories/pre/group_vars/vault.yml

ansible-playbook -i inventories/pre forbidden_hosts.yml --ask-vault-pass
```

### Via AAP

Créer un **Job Template** pointant sur ce playbook avec l'inventaire `pre`.
Planifier via un workflow ou un schedule AAP (ex : chaque lundi à 08h00).

---

## Résultat attendu

- **Aucune violation** : aucun email, message console `aucune`.
- **Violation détectée** : un email par org concernée, avec tableau `Inventaire | Nb hosts | Hosts interdits`.
