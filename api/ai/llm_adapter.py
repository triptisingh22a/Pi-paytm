from ai.number_guard import guarded


class LLMAdapter:
    status = "MOCKED"

    def explain(self, tool, receipt, language="en"):
        out = receipt.output
        if out.get("verdict") == "INSUFFICIENT_DATA":
            text = "I need item costs and matching experiment history before recommending this decision."
        elif tool == "promo":
            amount = out["incremental_profit"]
            if language == "hi":
                text = f"फ़ैसला: {out['verdict']}। बिना ऑफर की तुलना में अनुमानित मुनाफ़े का अंतर ₹{amount:,.2f} है। गणित में छूट और आगे की बिक्री का असर शामिल है।"
            elif language == "mr":
                text = f"निर्णय: {out['verdict']}। ऑफर न देण्याच्या तुलनेत अंदाजे नफ्यात ₹{amount:,.2f} फरक आहे। गणितात सवलत आणि पुढील विक्रीचा परिणाम आहे."
            else:
                text = f"{out['verdict']}. Estimated profit change versus doing nothing: ₹{amount:,.2f}. This includes discounts on existing sales and displaced future sales."
        elif tool == "cash":
            text = f"Safely committable cash under the model: ₹{out['safe_to_commit']:,.2f}. Recorded liabilities and settlement delays are included."
        elif tool == "allocate":
            text = f"Commit ₹{out['spend']:,.2f} to the suggested basket. Estimated incremental contribution: ₹{out['expected_incremental_profit']:,.2f}; check the twin before approving."
        elif tool == "overview":
            text = f"Recorded sales: ₹{out['sales']:,.2f}. These cover the observed payment channel; review item details below."
        elif tool == "peers":
            text = f"The anonymized group contains {out['group_size']} similar shops. Use the aggregate as a cold-start prior, not a promise of demand."
        elif tool == "loan":
            text = (
                "A lending-partner illustration is available with consent."
                if out["show"]
                else "No lending illustration meets the model conditions."
            )
        else:
            text = "Ask about restocking, discounts, cash, similar shops or your business overview."
        return guarded(text, receipt.model_dump(), text)[0]
