import { LegalLayout, Section } from "../components/LegalLayout";

const CONTACT = "support@finwingnews.com";

export default function Terms() {
  return (
    <LegalLayout title="Terms of Service" updated="June 23, 2026">
      <p>
        These Terms of Service (&ldquo;Terms&rdquo;) govern your access to and use of FinWing (the
        &ldquo;Service&rdquo;) at <span className="font-medium text-ink-800">finwingnews.com</span>.
        Please read them carefully.
      </p>

      <Section heading="1. Acceptance of Terms">
        <p>
          By accessing or using the Service, you agree to be bound by these Terms. If you do not
          agree, do not use the Service.
        </p>
      </Section>

      <Section heading="2. The Service">
        <p>
          FinWing aggregates publicly available financial news, matches it to the topics and assets
          you choose (&ldquo;lenses&rdquo;), and generates AI-assisted summaries. It may send you
          daily summary emails based on your preferences.
        </p>
      </Section>

      <Section heading="3. Not Financial Advice">
        <p>
          FinWing provides general information for educational and informational purposes only. It is
          <span className="font-medium text-ink-800"> not investment, financial, legal, or tax advice</span>,
          and nothing in the Service is a recommendation to buy, sell, or hold any security or asset.
          Investing involves risk, including the possible loss of principal. You are solely
          responsible for your own decisions and should consult a licensed professional before making
          any investment decision.
        </p>
      </Section>

      <Section heading="4. AI-Generated Content">
        <p>
          Summaries and other outputs are produced by automated AI systems and may be inaccurate,
          incomplete, or out of date. Always verify important information against primary sources. We
          do not guarantee the accuracy or completeness of any content.
        </p>
      </Section>

      <Section heading="5. Accounts">
        <p>
          You must provide accurate information and keep your login credentials secure. You are
          responsible for activity under your account. You must be at least 13 years old (or the age
          of majority where required) to use the Service.
        </p>
      </Section>

      <Section heading="6. Acceptable Use">
        <p>
          You agree not to misuse the Service, including: using it for any unlawful purpose;
          attempting to disrupt, reverse-engineer, or gain unauthorized access to it; scraping or
          overloading it; or infringing the rights of others.
        </p>
      </Section>

      <Section heading="7. Intellectual Property">
        <p>
          News headlines and articles belong to their respective publishers; FinWing surfaces
          excerpts, summaries, and links to original sources. The FinWing name, logo, and software are
          owned by us. We grant you a limited, personal, non-transferable, revocable license to use
          the Service for its intended purpose.
        </p>
      </Section>

      <Section heading="8. Third-Party Content and Links">
        <p>
          The Service references third-party news sources and may link to external sites. We are not
          responsible for the content, accuracy, or practices of any third-party source or site.
        </p>
      </Section>

      <Section heading="9. Disclaimers">
        <p className="uppercase">
          The Service is provided &ldquo;as is&rdquo; and &ldquo;as available&rdquo; without
          warranties of any kind, express or implied, including the implied warranties of
          merchantability, fitness for a particular purpose, and non-infringement.
        </p>
      </Section>

      <Section heading="10. Limitation of Liability">
        <p className="uppercase">
          To the maximum extent permitted by law, FinWing and its operator will not be liable for any
          indirect, incidental, special, consequential, or punitive damages, or any loss of profits,
          data, or investment losses, arising from or related to your use of the Service.
        </p>
      </Section>

      <Section heading="11. Termination">
        <p>
          We may suspend or terminate your access at any time, including for any violation of these
          Terms. You may stop using the Service and request deletion of your account at any time.
        </p>
      </Section>

      <Section heading="12. Changes to the Terms">
        <p>
          We may update these Terms from time to time. We will revise the &ldquo;Last updated&rdquo;
          date above and, for material changes, provide additional notice. Your continued use of the
          Service after changes take effect constitutes acceptance.
        </p>
      </Section>

      <Section heading="13. Governing Law">
        <p>
          These Terms are governed by the laws of the State of Washington, USA, without regard to its
          conflict-of-laws rules.
        </p>
      </Section>

      <Section heading="14. Contact">
        <p>
          Questions about these Terms? Email{" "}
          <a className="text-wing-600 hover:underline" href={`mailto:${CONTACT}`}>{CONTACT}</a>.
        </p>
      </Section>
    </LegalLayout>
  );
}
