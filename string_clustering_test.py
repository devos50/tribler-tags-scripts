import numpy as np
from sklearn.cluster import AffinityPropagation
import distance

words = "hello1 hello2 fdasfs fdafdsfaf iiouiuio".split(" ")
words = np.asarray(words)
lev_similarity = -1 * np.array([
   [distance.levenshtein(w1, w2) for w1 in words]
   for w2 in words
])

affprop = AffinityPropagation(affinity = "precomputed", damping = 0.5)
affprop.fit(lev_similarity)
for cluster_id in np.unique(affprop.labels_):
   exemplar = words[affprop.cluster_centers_indices_[cluster_id]]
   cluster = np.unique(words[np.nonzero(affprop.labels_ == cluster_id)])
   cluster_str = ", ".join(cluster)
   print(" - *%s:* %s" % (exemplar, cluster_str))
