"""
Truy cập dữ liệu, dùng chung cho ld_server.py (Linked Data + giao diện web) và vidbp.py (terminal).

Hai chế độ, cùng một giao diện:
  RemoteStore  gửi truy vấn tới SPARQL endpoint (Fuseki, sau khi chạy load.py)
  LocalStore   nạp thẳng các file vào rdflib, KHÔNG cần Fuseki. Dùng đúng danh sách file
               và named graph của load.py, nên kết quả giống hệt khi chạy trên Fuseki.
"""
from pathlib import Path

import requests
from rdflib import BNode, Dataset, Graph, URIRef

HERE = Path(__file__).parent
BASE = "https://w3id.org/vi-dbpedia/"
G = BASE + "graph/"
DEFAULT_ENDPOINT = "http://localhost:3030/vi-dbpedia/sparql"

RDF_FORMATS = {  # media type -> (định dạng rdflib, đuôi file)
    "text/turtle": ("turtle", "ttl"),
    "application/n-triples": ("nt", "nt"),
    "application/ld+json": ("json-ld", "jsonld"),
    "application/rdf+xml": ("xml", "rdf"),
}
RESULT_FORMATS = {  # media type -> định dạng rdflib cho kết quả SELECT/ASK
    "application/sparql-results+json": "json",
    "application/sparql-results+xml": "xml",
    "text/csv": "csv",
}


def term_json(t):
    """Một term rdflib -> dạng JSON giống chuẩn SPARQL 1.1 Query Results JSON."""
    if isinstance(t, URIRef):
        return {"type": "uri", "value": str(t)}
    if isinstance(t, BNode):
        return {"type": "bnode", "value": str(t)}
    d = {"type": "literal", "value": str(t)}
    if t.language:
        d["xml:lang"] = t.language
    elif t.datatype:
        d["datatype"] = str(t.datatype)
    return d


class RemoteStore:
    def __init__(self, endpoint=DEFAULT_ENDPOINT, timeout=120):
        self.endpoint, self.timeout = endpoint, timeout
        self.label = endpoint

    def _post(self, query, accept):
        try:
            r = requests.post(self.endpoint, data={"query": query},
                              headers={"Accept": accept}, timeout=self.timeout)
        except requests.ConnectionError:
            raise ConnectionError(
                f"Không kết nối được {self.endpoint}. Fuseki chưa chạy? "
                "Chạy start_fuseki (xem serve/README.md) hoặc dùng --local.") from None
        if r.status_code >= 400:
            raise ValueError(f"Endpoint trả lỗi {r.status_code}: {r.text[:500]}")
        return r

    def select(self, query):
        """-> (danh sách biến, danh sách dòng {biến: term_json}); ASK -> ([], bool)."""
        j = self._post(query, "application/sparql-results+json").json()
        if "boolean" in j:
            return [], j["boolean"]
        return j["head"]["vars"], j["results"]["bindings"]

    def construct(self, query):
        g = Graph()
        g.parse(data=self._post(query, "application/n-triples").text, format="nt")
        return g

    def raw(self, query, accept):
        r = self._post(query, accept)
        return r.content, r.headers.get("Content-Type", "application/octet-stream")


class LocalStore:
    def __init__(self):
        from load import plan  # cùng danh sách file và named graph với khi nạp vào Fuseki
        self.ds = Dataset(default_union=True)
        n = 0
        for name, files in plan().items():
            g = self.ds.graph(URIRef(G + name))
            for f in files:
                if f.exists():
                    g.parse(f)
            n += len(g)
        self.label = f"rdflib cục bộ ({n:,} triple)"

    def select(self, query):
        res = self.ds.query(query)
        if res.type == "ASK":
            return [], bool(res.askAnswer)
        names = [str(v) for v in res.vars]
        rows = [{v: term_json(row[i]) for i, v in enumerate(names) if row[i] is not None}
                for row in res]
        return names, rows

    def construct(self, query):
        return self.ds.query(query).graph

    def raw(self, query, accept):
        res = self.ds.query(query)
        if res.type in ("CONSTRUCT", "DESCRIBE"):
            mt = next((m for m in RDF_FORMATS if m in accept), "text/turtle")
            return res.graph.serialize(format=RDF_FORMATS[mt][0]).encode("utf-8"), mt
        mt = next((m for m in RESULT_FORMATS if m in accept), "application/sparql-results+json")
        out = res.serialize(format=RESULT_FORMATS[mt])
        return (out if isinstance(out, bytes) else out.encode("utf-8")), mt


def open_store(local=False, endpoint=DEFAULT_ENDPOINT):
    return LocalStore() if local else RemoteStore(endpoint)
