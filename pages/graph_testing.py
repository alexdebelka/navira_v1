import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("/Users/alexdebelka/Downloads/navira/new_data/ACTIVITY/TAB_APP_HOP_YEAR.csv")
d = (df.assign(finess=df["finessGeoDP"].astype(str).str.zfill(9))
       .query("finess == '930100037'")
       .groupby("annee", as_index=False)["n"].sum()
       .sort_values("annee"))

plt.bar(d["annee"], d["n"])
plt.xlabel("Year"); plt.ylabel("Activity (n)")
plt.title("FINESS 930100037 — Activity by Year")
plt.tight_layout(); plt.show()
