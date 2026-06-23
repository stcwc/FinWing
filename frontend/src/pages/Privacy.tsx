import { LegalLayout, Section } from "../components/LegalLayout";

const CONTACT = "support@finwingnews.com";

export default function Privacy() {
  return (
    <LegalLayout title="Privacy Policy" updated="June 23, 2026">
      <p>
        This Privacy Policy explains how FinWing (&ldquo;FinWing,&rdquo; &ldquo;we,&rdquo; &ldquo;us&rdquo;)
        collects, uses, and shares information when you use the FinWing service at{" "}
        <span className="font-medium text-ink-800">finwingnews.com</span> (the &ldquo;Service&rdquo;).
        FinWing is an AI-assisted financial-news aggregator that matches public news to topics
        and assets you choose and generates daily summaries.
      </p>

      <Section heading="1. Information We Collect">
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <span className="font-medium text-ink-800">Account information.</span> When you sign in
            with Google or with an email address, we receive your email address and, for Google
            sign-in, your name. Authentication is managed through Amazon Cognito.
          </li>
          <li>
            <span className="font-medium text-ink-800">Preferences and content you create.</span> The
            &ldquo;lenses&rdquo; (topics and assets) you follow, your timezone, language, summary-time
            preference, and whether you want daily summary emails.
          </li>
          <li>
            <span className="font-medium text-ink-800">Technical data.</span> A session cookie and
            basic request logs needed to operate and secure the Service. We do not use third-party
            advertising or cross-site analytics trackers.
          </li>
        </ul>
      </Section>

      <Section heading="2. How We Use Information">
        <ul className="list-disc space-y-1 pl-5">
          <li>To provide and personalize the Service — match news to your lenses and generate summaries.</li>
          <li>
            To send you daily summary emails when enabled. You can opt out at any time in Settings or
            via the unsubscribe link in any email.
          </li>
          <li>To maintain the security, reliability, and quality of the Service.</li>
        </ul>
      </Section>

      <Section heading="3. AI Processing">
        <p>
          We use Anthropic&rsquo;s Claude API to generate news summaries and related features. Article
          text and your lens configuration (topic and asset names) are sent to Anthropic for
          processing. We do not send your email address or account identifiers to the AI provider for
          summary generation, and your content is not used to train third-party models.
        </p>
      </Section>

      <Section heading="4. How We Share Information">
        <p>
          We do not sell your personal information. We share data only with the service providers that
          help us operate the Service:
        </p>
        <ul className="list-disc space-y-1 pl-5">
          <li><span className="font-medium text-ink-800">Google</span> — authentication, if you choose Google sign-in.</li>
          <li>
            <span className="font-medium text-ink-800">Amazon Web Services (AWS)</span> — hosting,
            database, and email delivery (Amazon SES). Data is stored in the United States.
          </li>
          <li><span className="font-medium text-ink-800">Anthropic</span> — AI processing as described above.</li>
        </ul>
        <p>
          We may disclose information if required to do so by law or to protect the rights, safety, or
          security of FinWing or its users.
        </p>
        <p>
          FinWing&rsquo;s use of information received from Google APIs adheres to the{" "}
          <a
            className="text-wing-600 hover:underline"
            href="https://developers.google.com/terms/api-services-user-data-policy"
            target="_blank"
            rel="noreferrer"
          >
            Google API Services User Data Policy
          </a>
          , including the Limited Use requirements.
        </p>
      </Section>

      <Section heading="5. Cookies">
        <p>
          We use a single, essential session cookie (httpOnly) to keep you signed in. We do not use
          advertising or cross-site tracking cookies.
        </p>
      </Section>

      <Section heading="6. Data Retention">
        <ul className="list-disc space-y-1 pl-5">
          <li>Aggregated news articles are retained for approximately 30 days.</li>
          <li>Your account and preferences are retained until you delete your account or ask us to delete them.</li>
        </ul>
      </Section>

      <Section heading="7. Your Choices and Rights">
        <ul className="list-disc space-y-1 pl-5">
          <li><span className="font-medium text-ink-800">Email summaries.</span> Opt out anytime in Settings or via the unsubscribe link.</li>
          <li>
            <span className="font-medium text-ink-800">Access and deletion.</span> Email us at{" "}
            <a className="text-wing-600 hover:underline" href={`mailto:${CONTACT}`}>{CONTACT}</a> to
            access or delete the personal data associated with your account.
          </li>
        </ul>
      </Section>

      <Section heading="8. Security">
        <p>
          We use industry-standard measures — encryption in transit, access controls, and managed AWS
          infrastructure — to protect your data. No method of transmission or storage is completely
          secure, and we cannot guarantee absolute security.
        </p>
      </Section>

      <Section heading="9. Children's Privacy">
        <p>
          FinWing is not directed to children under 13 (or the minimum age required in your
          jurisdiction), and we do not knowingly collect personal data from them.
        </p>
      </Section>

      <Section heading="10. International Users">
        <p>
          The Service is operated from the United States. By using it, you understand that your
          information will be processed in the United States.
        </p>
      </Section>

      <Section heading="11. Changes to This Policy">
        <p>
          We may update this Privacy Policy from time to time. We will revise the &ldquo;Last
          updated&rdquo; date above and, for material changes, provide additional notice.
        </p>
      </Section>

      <Section heading="12. Contact">
        <p>
          Questions about this policy? Email{" "}
          <a className="text-wing-600 hover:underline" href={`mailto:${CONTACT}`}>{CONTACT}</a>.
        </p>
      </Section>
    </LegalLayout>
  );
}
