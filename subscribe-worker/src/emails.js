import { SITE, esc, baseURL } from "./common.js";
const shell = (title, body, unsubscribe) =>
  `<!doctype html><html><body style="margin:0;background:#f4f1ea;color:#1e2d33;font:16px/1.6 Arial,sans-serif"><div style="max-width:560px;margin:24px auto;padding:28px;background:#fff;border-radius:12px"><p style="font-weight:bold;font-size:23px;margin:0 0 22px">🦉 News <span style="color:#e95349">Pebbles</span></p><h1 style="font-size:23px;line-height:1.3">${esc(title)}</h1>${body}<hr style="border:0;border-top:1px solid #ded8cb;margin:25px 0"><p style="font-size:13px;color:#5e6a70">Sent to a parent who requested News Pebbles. <a href="${esc(unsubscribe)}">Unsubscribe</a><br>News Pebbles · NeRDLabs · <a href="${SITE}/privacy.html">Privacy</a></p></div></body></html>`;
function envelope(env, sub, subject) {
  const unsubscribe = `${baseURL(env)}/api/unsubscribe?token=${sub.unsubscribe_token}`;
  return {
    unsubscribe,
    payload: {
      from: env.RESEND_FROM,
      to: [sub.email],
      reply_to: "info@newspebbles.com",
      subject,
      headers: {
        "List-Unsubscribe": `<${unsubscribe}>`,
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
      },
    },
  };
}
export function confirmationEmail(env, sub, name) {
  const { payload, unsubscribe } = envelope(
    env,
    sub,
    "Confirm your News Pebbles delivery",
  );
  const verify = `${baseURL(env)}/api/verify?token=${sub.verify_token}`;
  const cadence =
    sub.cadence === "every_issue"
      ? "whenever a new issue is published"
      : "once a week on weekends";
  const body = `<p>Hello,</p><p>Would you like <strong>${esc(name)}</strong> delivered ${cadence}?</p><p>Confirm your email and we’ll send the current paper as a welcome gift, ready to print or enjoy in Read &amp; Play.</p><p><a href="${esc(verify)}" style="display:inline-block;padding:12px 18px;background:#007b83;color:#fff;border-radius:8px;text-decoration:none;font-weight:bold">Confirm my subscription</a></p><p>This link expires in 24 hours. If you didn’t request this, simply ignore this email.</p>`;
  return {
    ...payload,
    html: shell("A little paper for your family", body, unsubscribe),
    text: `Hello,\nConfirm delivery of ${name} ${cadence}:\n${verify}\n\nWe’ll send the latest paper as a welcome gift. This link expires in 24 hours. Ignore this email if you did not request it.\nUnsubscribe: ${unsubscribe}`,
  };
}
export function issueEmail(env, sub, issue) {
  const { payload, unsubscribe } = envelope(
    env,
    sub,
    `${issue.name} · ${issue.date}`,
  );
  const whatsapp = `https://wa.me/?text=${encodeURIComponent(`${issue.name} (${issue.age}) · ${issue.date}\nRead & Play: ${issue.reader}\nPrintable PDF: ${issue.pdf}`)}`;
  const body = `<p>Hello,</p><p>Your family’s next little window on the world is here.</p><p><strong>${esc(issue.name)}</strong><br>${esc(issue.age)} · ${esc(issue.date)}</p><img src="${esc(issue.cover)}" width="140" alt="Front page of ${esc(issue.name)}" style="display:block;border:1px solid #ded8cb;margin:18px 0"><p><a href="${esc(issue.reader)}" style="display:inline-block;background:#007b83;color:#fff;padding:13px 18px;border-radius:8px;text-decoration:none;font-weight:bold">Open in Read &amp; Play (Audio + Quiz)</a></p><p><a href="${esc(issue.pdf)}" style="display:inline-block;border:1px solid #1e2d33;color:#1e2d33;padding:11px 18px;border-radius:8px;text-decoration:none">Download Printable PDF</a></p><p>The printable PDF is attached, too. Print it, put the screen away and discover something together.</p><p>Warmly,<br>News Pebbles</p><p><a href="${esc(whatsapp)}">Share on WhatsApp</a></p>`;
  return {
    ...payload,
    html: shell("Your paper is ready", body, unsubscribe),
    text: `Hello,\n\n${issue.name} · ${issue.age} · ${issue.date}\n\nOpen in Read & Play (Audio + Quiz): ${issue.reader}\nDownload Printable PDF: ${issue.pdf}\nThe PDF is also attached for printing or forwarding to your printer.\n\nShare on WhatsApp: ${whatsapp}\n\nWarmly,\nNews Pebbles\nUnsubscribe: ${unsubscribe}`,
  };
}
