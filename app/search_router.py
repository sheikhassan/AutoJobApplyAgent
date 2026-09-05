import logging, os
from .security import validate_external_url, SecurityError
from .exa_search import ExaJobSearcher

log=logging.getLogger(__name__)

class SearchRouter:
    """Production search failover: Exa first, TinyFish only on provider failure/empty result."""
    def __init__(self, config=None):
        self.config=config
        self.primary=ExaJobSearcher(config) if os.getenv('EXA_API_KEY') else None
        self.tinyfish_key=os.getenv('TINYFISH_API_KEY','')
        self.tinyfish_base=os.getenv('TINYFISH_BASE_URL','https://api.tinyfish.ai/v1').rstrip('/')

    def search_jobs(self, queries, max_results=5, query_budget=8):
        errors=[]
        if self.primary:
            try:
                jobs=self.primary.search_jobs(queries, max_results, query_budget)
                if jobs:
                    return jobs, 'exa', None
                errors.append('Exa returned no results')
            except Exception as exc:
                log.exception('Exa search failed; using TinyFish fallback')
                errors.append(f'Exa: {exc}')
        else:
            errors.append('EXA_API_KEY not configured')
        if self.tinyfish_key:
            try:
                jobs=self._tinyfish_search(list(queries)[:max(1,query_budget)], max_results)
                if jobs: return jobs, 'tinyfish', '; '.join(errors)
                errors.append('TinyFish returned no results')
            except Exception as exc:
                log.exception('TinyFish fallback failed')
                errors.append(f'TinyFish: {exc}')
        else:
            errors.append('TINYFISH_API_KEY not configured')
        raise RuntimeError('All search providers failed: ' + ' | '.join(errors))

    def fetch_contents(self, urls, limit=5):
        safe=[]
        for u in list(dict.fromkeys(urls))[:max(0,limit)]:
            try: safe.append(validate_external_url(u))
            except SecurityError: log.warning('Blocked unsafe content URL: %s', u[:120])
        urls=safe
        if not urls: return {}
        if self.primary:
            try: return self.primary.fetch_contents(urls, limit)
            except Exception: log.exception('Exa content fetch failed; using TinyFish Fetch')
        if not self.tinyfish_key: return {}
        import requests
        r=requests.post(f'{self.tinyfish_base}/fetch',headers={'X-API-Key':self.tinyfish_key,'Content-Type':'application/json'},json={'urls':urls},timeout=60)
        r.raise_for_status(); data=r.json(); results=data.get('results',data.get('data',[]))
        if isinstance(results,dict): results=results.get('results',[])
        out={}
        for x in results or []:
            u=x.get('url'); text=x.get('text') or x.get('content') or x.get('markdown') or ''
            if u and text: out[u]=text
        return out

    def _tinyfish_search(self, queries, max_results):
        import requests
        out=[]; seen=set()
        for q in queries:
            r=requests.post(f'{self.tinyfish_base}/search',headers={'X-API-Key':self.tinyfish_key,'Content-Type':'application/json'},json={'query':q,'max_results':max_results},timeout=45)
            r.raise_for_status(); data=r.json()
            results=data.get('results',data.get('data',[]))
            if isinstance(results,dict): results=results.get('results',[])
            for x in results or []:
                url=x.get('url') or x.get('link')
                if not url or url.lower().rstrip('/') in seen: continue
                seen.add(url.lower().rstrip('/'))
                out.append({'title':x.get('title',''),'url':url,'published_date':x.get('published_date') or x.get('date'),
                            'author':x.get('author'),'highlights':x.get('highlights') or ([x.get('snippet')] if x.get('snippet') else []),
                            'search_query':q,'source':'TinyFish / Web Search','source_category':'web_search'})
        return out
