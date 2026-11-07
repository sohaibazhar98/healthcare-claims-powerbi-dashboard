# LinkedIn post draft

Attach 2–3 screenshots of the report (Executive Overview first). Link the GitHub repo in the
first comment if you publish it there.

---

**New portfolio project: Large Group Health Plan Performance dashboard in Power BI 📊**

I built a three-page Power BI report that answers the questions underwriting and finance teams
ask about a fully insured book of business:

🔹 Is the book profitable, and is claims trend outrunning our rate increases?
🔹 Where are the claim dollars going, and how much do we lose to denials?
🔹 Which employer groups need rate action at renewal?

What the data showed:
📈 Loss ratio rose from 85.5% to 91.3% over three years, against an 85% target
📈 Rolling 12-month PMPM trend of +12%, while premium grew about 5–7% a year
💡 172 high-cost claimants (≥$100K) drove 21% of paid claims
💡 HMO plans ran at a 100% loss ratio, compared with 70% for HDHP
💡 7 of 33 groups were above 100%, which makes a clear renewal priority list

Under the hood:
✅ Star schema with two fact tables (claims and member months/premium) and conformed dimensions
✅ 58 DAX measures, including PMPM, rolling-12 trend, YoY, high-cost claimant logic,
   USERELATIONSHIP for paid-date vs incurred-date views, and measure-driven conditional formatting
✅ Power Query transformations with a parameterized data source
✅ Built as a Power BI Project (TMDL + PBIR), so the model and report are version-controlled text

The dataset is synthetic. I wrote a Python generator so it would behave like a real book of
business, with age/gender cost curves, seasonality, trend, deductibles and denials, and
without using any real member data.

I'm working toward the PL-300 certification, and this project let me practice the full
workflow, from data modeling to the final story. I'd welcome feedback from other BI and
healthcare analytics folks 👇

#PowerBI #DataAnalytics #HealthcareAnalytics #DAX #BusinessIntelligence #DataVisualization #PL300
