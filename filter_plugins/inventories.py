"""
filter_plugins/inventories.py — Détection des hosts interdits dans les inventaires AAP
=======================================================================================
Parcourt tous les inventaires de chaque organisation AAP et retourne ceux
qui contiennent des hosts appartenant au domaine de production interdit.

Usage Ansible :
    aap_organization_map | get_forbidden_hosts(aap_api, aap_token, forbidden_host_domain)

Retourne :
    dict { org_name: [ {inventory_id, inventory_name, hosts: [{id, name}]} ] }
    → clé absente ou liste vide = pas de violation pour cette org
"""

import requests
from urllib.parse import urljoin


# ======================================================================
# HELPERS PRIVÉS
# ======================================================================

def _headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _paginate(url, hdrs):
    """Itère sur toutes les pages d'un endpoint AAP paginé."""
    while url:
        try:
            resp = requests.get(url, headers=hdrs, verify=False, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[inventories.py] Erreur HTTP {url}: {e}")
            break
        yield from data.get("results", [])
        next_url = data.get("next")
        if next_url and not next_url.startswith("http"):
            next_url = urljoin(url, next_url)
        url = next_url


def _is_forbidden(hostname, domain):
    """
    True si le hostname appartient au domaine de production interdit.

    Exemples avec domain='sec-prod1.lan' :
        'myserver.sec-prod1.lan'   → True
        'sec-prod1.lan'            → True  (le domaine lui-même)
        'mysec-prod1.lan'          → False (préfixe sans point)
        'myserver.sec-prod1.lan.x' → False (domaine différent)
    """
    h = hostname.lower().strip()
    d = domain.lower().strip().lstrip(".")
    return h == d or h.endswith("." + d)


# ======================================================================
# FILTRE PRINCIPAL
# ======================================================================

def get_forbidden_hosts(orgs, api_url, token, domain):
    """
    Analyse tous les inventaires de chaque organisation AAP et retourne
    ceux qui contiennent des hosts appartenant au domaine interdit.

    Args:
        orgs    : liste de dicts {id, name, label, contact_email}
        api_url : URL base de l'API AAP (ex: https://aap.exemple.fr/api/v2)
        token   : Bearer token AAP
        domain  : domaine interdit (ex: sec-prod1.lan)

    Returns:
        dict { org_name: [ {inventory_id, inventory_name, hosts: [{id, name}]} ] }
    """
    if not api_url or not token or not domain:
        raise ValueError("[get_forbidden_hosts] api_url, token et domain sont requis")

    base_url = api_url.rstrip("/")
    hdrs     = _headers(token)
    result   = {}

    for org in orgs:
        org_id   = org["id"]
        org_name = org["name"]
        violations = []

        inventories_url = f"{base_url}/organizations/{org_id}/inventories/"

        for inventory in _paginate(inventories_url, hdrs):
            inv_id   = inventory["id"]
            inv_name = inventory["name"]

            forbidden_hosts = []
            hosts_url = f"{base_url}/inventories/{inv_id}/hosts/"

            for host in _paginate(hosts_url, hdrs):
                if _is_forbidden(host["name"], domain):
                    forbidden_hosts.append({
                        "id":   host["id"],
                        "name": host["name"],
                    })

            if forbidden_hosts:
                violations.append({
                    "inventory_id":   inv_id,
                    "inventory_name": inv_name,
                    "hosts":          forbidden_hosts,
                })

        if violations:
            result[org_name] = violations

    return result


# ======================================================================
# REGISTER
# ======================================================================

class FilterModule:
    def filters(self):
        return {
            "get_forbidden_hosts": get_forbidden_hosts,
        }
