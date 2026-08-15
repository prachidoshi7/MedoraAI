import medoraLogo from '../../../medora_logo-removebg-preview.png';
import medoraLoginLogo from '../../../medora_logo.jpeg';

type BrandLogoProps = {
  className?: string;
  variant?: 'default' | 'login';
};

export default function BrandLogo({ className = '', variant = 'default' }: BrandLogoProps) {
  const isLoginLogo = variant === 'login';

  return (
    <span className={`medora-logo ${className}`.trim()}>
      <img
        src={isLoginLogo ? medoraLoginLogo : medoraLogo}
        alt="MedoraAI logo"
        width={isLoginLogo ? 1536 : 608}
        height={isLoginLogo ? 1024 : 400}
        decoding="async"
      />
    </span>
  );
}
