import Link from "next/link";
import { ArrowRight, ArrowUpRight, Boxes, FlaskConical, Lock, Mic, ShieldCheck } from "lucide-react";

export default function Landing() {
  return (
    <main className="lp">
      <nav className="lp-nav">
        <Link className="brand" href="/">
          <span className="mark">π</span>pi
          <span className="brand-dot">.</span>
        </Link>
        <span className="lp-kicker">AI FOR MERCHANTS · PAYTM POS</span>
        <Link className="outline-link" href="/demo">
          Enter demo <ArrowUpRight size={16} />
        </Link>
      </nav>

      <section className="lp-hero">
        <div className="lp-copy">
          <div className="eyebrow">
            <span className="live-dot" /> AI INVENTORY + A DIGITAL TWIN OF YOUR SHOP
          </div>
          <h1>
            Know what to stock next, <span>before you spend.</span>
          </h1>
          <p>
            Pi reads your supplier bills and sales, keeps your inventory straight, and lets you test a stocking or price
            decision on a digital twin of your shop. Ask in text or voice; every answer comes from your own data.
          </p>
          <div className="lp-cta">
            <Link className="enter-demo" href="/demo">
              Enter demo <ArrowRight size={18} />
            </Link>
            <span className="lp-principle">Calculate. Explain. Decide.</span>
          </div>
          <div className="lp-pillars">
            <div>
              <Boxes size={18} />
              <strong>AI-assisted inventory</strong>
              <small>Replenish list with quantities, regulars, shelf checks</small>
            </div>
            <div>
              <FlaskConical size={18} />
              <strong>Digital twin</strong>
              <small>Test a restock, swap or price change before you commit</small>
            </div>
          </div>
        </div>

        <div className="lp-preview" aria-label="Example of Pi answering a merchant">
          <div className="lp-window">
            <div className="lp-window-bar">
              <i /> <i /> <i />
              <span>Ask Pi</span>
              <span className="lp-voice">
                <Mic size={12} /> text or voice
              </span>
            </div>
            <div className="lp-chat">
              <div className="lp-bubble user">What should I reorder this week?</div>
              <div className="lp-bubble pi">
                Oats 1 kg and Potato chips 50 g are running low. About <b>257</b> more Oats and <b>218</b> more chips would
                cover the next 14 days.
                <span className="lp-chip">insight.restock · from your bills and sales</span>
              </div>
              <div className="lp-bubble user">If I sell Rice 5 kg at ₹500, will I make more?</div>
              <div className="lp-bubble pi">
                You would need at least <b>146</b> sales to beat today's <b>₹10,170</b> contribution. Rice has only ever sold at
                one price, so I can't yet say if that is achievable.
                <span className="lp-chip warn">
                  <Lock size={11} /> forecast withheld · no price history
                </span>
              </div>
            </div>
          </div>
          <div className="lp-float">
            <span>Every number</span>
            <strong>has a receipt</strong>
          </div>
        </div>
      </section>

      <footer className="lp-foot">
        <span>
          <ShieldCheck size={14} /> Answers come from tools that read your data, not from guesses
        </span>
        <span>Hackathon prototype · all merchant data is simulated</span>
      </footer>
    </main>
  );
}
