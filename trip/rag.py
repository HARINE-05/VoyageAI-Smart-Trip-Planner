"""Local TF-IDF retrieval: no embedding API or downloaded model required."""
import json
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class KnowledgeBase:
    def __init__(self):
        self.docs = json.loads((Path(__file__).resolve().parents[1] / 'data/knowledge.json').read_text())
        self.vectorizer = TfidfVectorizer(stop_words='english', ngram_range=(1, 2))
        self.matrix = self.vectorizer.fit_transform([d['title'] + ' ' + d['text'] for d in self.docs])

    def search(self, query, k=5):
        scores = cosine_similarity(self.vectorizer.transform([query]), self.matrix)[0]
        cities = {d.get('destination') for d in self.docs if d.get('destination') and d['destination'].lower() in query.lower()}
        ranked = [i for i in scores.argsort()[::-1] if scores[i] > 0
                  and (not cities or self.docs[i].get('destination') in cities or not self.docs[i].get('destination'))]
        return [dict(self.docs[i], score=round(float(scores[i]), 3)) for i in ranked[:k]]
