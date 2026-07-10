import { motion } from 'framer-motion';

interface TypingIndicatorProps {
  isDm?: boolean;
  hasAssistantMessage?: boolean;
}

export default function TypingIndicator({ isDm = false, hasAssistantMessage = false }: TypingIndicatorProps) {
  const dotColor = isDm ? 'bg-dm-400' : 'bg-primary-500';
  const textColor = isDm ? 'text-dm-200' : 'text-gray-500';
  const bgColor = isDm ? 'bg-dm-800' : 'bg-white';
  
  const statusText = hasAssistantMessage ? '正在输入中...' : '正在思考中...';

  return (
    <div className="flex justify-start">
      <div className={`rounded-2xl px-4 py-3 shadow-md ${bgColor}`}>
        <div className="flex items-center gap-3">
          <div className="flex gap-1.5">
            {[0, 1, 2].map((i) => (
              <motion.div
                key={i}
                className={`w-2.5 h-2.5 rounded-full ${dotColor}`}
                animate={{
                  y: [0, -8, 0],
                  opacity: [0.4, 1, 0.4],
                }}
                transition={{
                  duration: 0.6,
                  repeat: Infinity,
                  ease: 'easeInOut',
                  delay: i * 0.15,
                }}
              />
            ))}
          </div>
          <span className={`text-sm font-medium ${textColor}`}>
            {statusText}
          </span>
        </div>
      </div>
    </div>
  );
}
