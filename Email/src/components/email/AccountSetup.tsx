import React, { useState } from 'react';
import { 
  Mail, 
  Server, 
  Lock, 
  User, 
  Settings, 
  CheckCircle, 
  AlertCircle,
  Loader2,
  Eye,
  EyeOff
} from 'lucide-react';
import { clsx } from 'clsx';
import { EmailAccount, EMAIL_PROVIDERS, EmailProvider } from '../../types/imap';
import { IMAPService } from '../../services/imapService';

interface AccountSetupProps {
  onAccountAdded: (accountId: string) => void;
  onCancel: () => void;
  className?: string;
}

interface FormData {
  name: string;
  email: string;
  password: string;
  provider: EmailProvider | 'custom';
  customImap: {
    server: string;
    port: number;
    use_tls: boolean;
  };
  customSmtp: {
    server: string;
    port: number;
    use_tls: boolean;
  };
}

const initialFormData: FormData = {
  name: '',
  email: '',
  password: '',
  provider: 'gmail',
  customImap: {
    server: '',
    port: 993,
    use_tls: true,
  },
  customSmtp: {
    server: '',
    port: 587,
    use_tls: true,
  },
};

export const AccountSetup: React.FC<AccountSetupProps> = ({
  onAccountAdded,
  onCancel,
  className
}) => {
  const [formData, setFormData] = useState<FormData>(initialFormData);
  const [step, setStep] = useState<'basic' | 'advanced' | 'testing'>('basic');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [testResult, setTestResult] = useState<'success' | 'error' | null>(null);

  const handleInputChange = (field: keyof FormData, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    setError(null);
  };

  const handleNestedInputChange = (
    parent: 'customImap' | 'customSmtp',
    field: string,
    value: any
  ) => {
    setFormData(prev => ({
      ...prev,
      [parent]: { ...prev[parent], [field]: value }
    }));
    setError(null);
  };

  const validateBasicInfo = (): boolean => {
    if (!formData.name.trim()) {
      setError('Account name is required');
      return false;
    }
    if (!formData.email.trim()) {
      setError('Email address is required');
      return false;
    }
    if (!formData.password.trim()) {
      setError('Password is required');
      return false;
    }
    
    // Basic email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(formData.email)) {
      setError('Please enter a valid email address');
      return false;
    }
    
    return true;
  };

  const validateAdvancedSettings = (): boolean => {
    if (formData.provider === 'custom') {
      if (!formData.customImap.server.trim()) {
        setError('IMAP server is required');
        return false;
      }
      if (!formData.customSmtp.server.trim()) {
        setError('SMTP server is required');
        return false;
      }
      if (formData.customImap.port < 1 || formData.customImap.port > 65535) {
        setError('IMAP port must be between 1 and 65535');
        return false;
      }
      if (formData.customSmtp.port < 1 || formData.customSmtp.port > 65535) {
        setError('SMTP port must be between 1 and 65535');
        return false;
      }
    }
    return true;
  };

  const buildAccountConfig = (): Omit<EmailAccount, 'id'> => {
    const isCustom = formData.provider === 'custom';
    const providerConfig = isCustom ? null : EMAIL_PROVIDERS[formData.provider];
    
    return {
      name: formData.name,
      email: formData.email,
      username: formData.email, // Most providers use email as username
      encrypted_password: formData.password, // TODO: Encrypt password
      imap_server: isCustom ? formData.customImap.server : providerConfig!.imap.server,
      imap_port: isCustom ? formData.customImap.port : providerConfig!.imap.port,
      smtp_server: isCustom ? formData.customSmtp.server : providerConfig!.smtp.server,
      smtp_port: isCustom ? formData.customSmtp.port : providerConfig!.smtp.port,
      use_tls: isCustom ? formData.customImap.use_tls : providerConfig!.imap.use_tls,
    };
  };

  const testConnection = async () => {
    if (!validateBasicInfo() || !validateAdvancedSettings()) {
      return;
    }

    setLoading(true);
    setError(null);
    setTestResult(null);
    setStep('testing');

    try {
      const accountConfig = buildAccountConfig();
      const isValid = await IMAPService.validateAccount(accountConfig);
      
      if (isValid) {
        setTestResult('success');
      } else {
        setTestResult('error');
        setError('Connection test failed. Please check your settings.');
      }
    } catch (error) {
      setTestResult('error');
      setError(`Connection test failed: ${error}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!validateBasicInfo() || !validateAdvancedSettings()) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const accountConfig = buildAccountConfig();
      const accountId = await IMAPService.addAccount(accountConfig);
      onAccountAdded(accountId);
    } catch (error) {
      setError(`Failed to add account: ${error}`);
    } finally {
      setLoading(false);
    }
  };

  const renderBasicStep = () => (
    <div className="space-y-6">
      <div className="text-center mb-6">
        <Mail className="w-12 h-12 text-accent-500 mx-auto mb-3" />
        <h2 className="text-xl font-semibold text-primary-50 mb-2">
          Add Email Account
        </h2>
        <p className="text-surface-400">
          Enter your email credentials to get started
        </p>
      </div>

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-surface-300 mb-2">
            Account Name
          </label>
          <input
            type="text"
            value={formData.name}
            onChange={(e) => handleInputChange('name', e.target.value)}
            placeholder="My Work Email"
            className="w-full px-3 py-2 bg-surface-800 border border-surface-600 rounded-lg text-primary-50 placeholder-surface-400 focus:border-accent-500 focus:outline-none"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-surface-300 mb-2">
            Email Address
          </label>
          <input
            type="email"
            value={formData.email}
            onChange={(e) => handleInputChange('email', e.target.value)}
            placeholder="your.email@example.com"
            className="w-full px-3 py-2 bg-surface-800 border border-surface-600 rounded-lg text-primary-50 placeholder-surface-400 focus:border-accent-500 focus:outline-none"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-surface-300 mb-2">
            Password
          </label>
          <div className="relative">
            <input
              type={showPassword ? 'text' : 'password'}
              value={formData.password}
              onChange={(e) => handleInputChange('password', e.target.value)}
              placeholder="Your email password"
              className="w-full px-3 py-2 pr-10 bg-surface-800 border border-surface-600 rounded-lg text-primary-50 placeholder-surface-400 focus:border-accent-500 focus:outline-none"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 transform -translate-y-1/2 text-surface-400 hover:text-surface-300"
            >
              {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-surface-300 mb-2">
            Email Provider
          </label>
          <select
            value={formData.provider}
            onChange={(e) => handleInputChange('provider', e.target.value as EmailProvider | 'custom')}
            className="w-full px-3 py-2 bg-surface-800 border border-surface-600 rounded-lg text-primary-50 focus:border-accent-500 focus:outline-none"
          >
            {Object.entries(EMAIL_PROVIDERS).map(([key, provider]) => (
              <option key={key} value={key}>
                {provider.name}
              </option>
            ))}
            <option value="custom">Custom Settings</option>
          </select>
        </div>
      </div>

      <div className="flex justify-between pt-4">
        <button
          onClick={onCancel}
          className="px-4 py-2 text-surface-400 hover:text-surface-300 transition-colors"
        >
          Cancel
        </button>
        <div className="space-x-3">
          {formData.provider === 'custom' && (
            <button
              onClick={() => setStep('advanced')}
              className="px-4 py-2 bg-surface-700 hover:bg-surface-600 text-primary-50 rounded-lg transition-colors"
            >
              Advanced Settings
            </button>
          )}
          <button
            onClick={testConnection}
            disabled={loading}
            className="px-4 py-2 bg-accent-500 hover:bg-accent-600 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              'Test Connection'
            )}
          </button>
        </div>
      </div>
    </div>
  );

  const renderAdvancedStep = () => (
    <div className="space-y-6">
      <div className="text-center mb-6">
        <Settings className="w-12 h-12 text-accent-500 mx-auto mb-3" />
        <h2 className="text-xl font-semibold text-primary-50 mb-2">
          Advanced Settings
        </h2>
        <p className="text-surface-400">
          Configure custom IMAP and SMTP settings
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* IMAP Settings */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-primary-50 flex items-center">
            <Server className="w-5 h-5 mr-2" />
            IMAP Settings
          </h3>
          
          <div>
            <label className="block text-sm font-medium text-surface-300 mb-2">
              IMAP Server
            </label>
            <input
              type="text"
              value={formData.customImap.server}
              onChange={(e) => handleNestedInputChange('customImap', 'server', e.target.value)}
              placeholder="imap.example.com"
              className="w-full px-3 py-2 bg-surface-800 border border-surface-600 rounded-lg text-primary-50 placeholder-surface-400 focus:border-accent-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-surface-300 mb-2">
              IMAP Port
            </label>
            <input
              type="number"
              value={formData.customImap.port}
              onChange={(e) => handleNestedInputChange('customImap', 'port', parseInt(e.target.value))}
              placeholder="993"
              className="w-full px-3 py-2 bg-surface-800 border border-surface-600 rounded-lg text-primary-50 placeholder-surface-400 focus:border-accent-500 focus:outline-none"
            />
          </div>

          <div className="flex items-center">
            <input
              type="checkbox"
              id="imap-tls"
              checked={formData.customImap.use_tls}
              onChange={(e) => handleNestedInputChange('customImap', 'use_tls', e.target.checked)}
              className="rounded border-surface-600 bg-surface-700 text-accent-500 focus:ring-accent-500"
            />
            <label htmlFor="imap-tls" className="ml-2 text-sm text-surface-300">
              Use TLS/SSL
            </label>
          </div>
        </div>

        {/* SMTP Settings */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-primary-50 flex items-center">
            <Mail className="w-5 h-5 mr-2" />
            SMTP Settings
          </h3>
          
          <div>
            <label className="block text-sm font-medium text-surface-300 mb-2">
              SMTP Server
            </label>
            <input
              type="text"
              value={formData.customSmtp.server}
              onChange={(e) => handleNestedInputChange('customSmtp', 'server', e.target.value)}
              placeholder="smtp.example.com"
              className="w-full px-3 py-2 bg-surface-800 border border-surface-600 rounded-lg text-primary-50 placeholder-surface-400 focus:border-accent-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-surface-300 mb-2">
              SMTP Port
            </label>
            <input
              type="number"
              value={formData.customSmtp.port}
              onChange={(e) => handleNestedInputChange('customSmtp', 'port', parseInt(e.target.value))}
              placeholder="587"
              className="w-full px-3 py-2 bg-surface-800 border border-surface-600 rounded-lg text-primary-50 placeholder-surface-400 focus:border-accent-500 focus:outline-none"
            />
          </div>

          <div className="flex items-center">
            <input
              type="checkbox"
              id="smtp-tls"
              checked={formData.customSmtp.use_tls}
              onChange={(e) => handleNestedInputChange('customSmtp', 'use_tls', e.target.checked)}
              className="rounded border-surface-600 bg-surface-700 text-accent-500 focus:ring-accent-500"
            />
            <label htmlFor="smtp-tls" className="ml-2 text-sm text-surface-300">
              Use TLS/SSL
            </label>
          </div>
        </div>
      </div>

      <div className="flex justify-between pt-4">
        <button
          onClick={() => setStep('basic')}
          className="px-4 py-2 text-surface-400 hover:text-surface-300 transition-colors"
        >
          Back
        </button>
        <button
          onClick={testConnection}
          disabled={loading}
          className="px-4 py-2 bg-accent-500 hover:bg-accent-600 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
        >
          {loading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            'Test Connection'
          )}
        </button>
      </div>
    </div>
  );

  const renderTestingStep = () => (
    <div className="space-y-6">
      <div className="text-center mb-6">
        {loading ? (
          <Loader2 className="w-12 h-12 text-accent-500 mx-auto mb-3 animate-spin" />
        ) : testResult === 'success' ? (
          <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-3" />
        ) : (
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-3" />
        )}
        
        <h2 className="text-xl font-semibold text-primary-50 mb-2">
          {loading ? 'Testing Connection...' : 
           testResult === 'success' ? 'Connection Successful!' : 
           'Connection Failed'}
        </h2>
        
        <p className="text-surface-400">
          {loading ? 'Please wait while we test your email settings' :
           testResult === 'success' ? 'Your email account is ready to be added' :
           'Please check your settings and try again'}
        </p>
      </div>

      {testResult === 'success' && (
        <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-4">
          <div className="flex items-center text-green-400 mb-2">
            <CheckCircle className="w-5 h-5 mr-2" />
            <span className="font-medium">Connection Details</span>
          </div>
          <div className="text-sm text-surface-300 space-y-1">
            <div>Email: {formData.email}</div>
            <div>Provider: {formData.provider === 'custom' ? 'Custom' : EMAIL_PROVIDERS[formData.provider].name}</div>
            <div>IMAP: {formData.provider === 'custom' ? formData.customImap.server : EMAIL_PROVIDERS[formData.provider].imap.server}</div>
          </div>
        </div>
      )}

      <div className="flex justify-between pt-4">
        <button
          onClick={() => setStep(formData.provider === 'custom' ? 'advanced' : 'basic')}
          disabled={loading}
          className="px-4 py-2 text-surface-400 hover:text-surface-300 transition-colors disabled:opacity-50"
        >
          Back
        </button>
        
        {testResult === 'success' ? (
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="px-4 py-2 bg-accent-500 hover:bg-accent-600 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              'Add Account'
            )}
          </button>
        ) : (
          <button
            onClick={testConnection}
            disabled={loading}
            className="px-4 py-2 bg-accent-500 hover:bg-accent-600 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              'Retry Test'
            )}
          </button>
        )}
      </div>
    </div>
  );

  return (
    <div className={clsx('bg-surface-900 rounded-lg p-6 max-w-2xl mx-auto', className)}>
      {error && (
        <div className="mb-6 bg-red-500/10 border border-red-500/20 rounded-lg p-4">
          <div className="flex items-center text-red-400">
            <AlertCircle className="w-5 h-5 mr-2" />
            <span className="font-medium">Error</span>
          </div>
          <p className="text-sm text-red-300 mt-1">{error}</p>
        </div>
      )}

      {step === 'basic' && renderBasicStep()}
      {step === 'advanced' && renderAdvancedStep()}
      {step === 'testing' && renderTestingStep()}
    </div>
  );
};

export default AccountSetup;