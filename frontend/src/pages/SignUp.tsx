import {
  Box,
  Button,
  Container,
  FormControl,
  FormErrorMessage,
  FormLabel,
  Heading,
  Input,
  Stack,
  Text,
  useToast,
  VStack,
} from "@chakra-ui/react"
import { Link } from "@tanstack/react-router"
import { useForm } from "react-hook-form"
import useAuth from "../hooks/useAuth"

interface SignUpForm {
  email: string
  password: string
  confirmPassword: string
  inviteCode: string  // 新增邀请码字段
}

export default function SignUp() {
  const { signUpMutation } = useAuth()
  const toast = useToast()

  const {
    handleSubmit,
    register,
    formState: { errors },
    watch,
  } = useForm<SignUpForm>()

  const password = watch("password")

  const onSubmit = async (data: SignUpForm) => {
    try {
      await signUpMutation.mutateAsync({
        email: data.email,
        password: data.password,
        invite_code: data.inviteCode,  // 添加邀请码
      })
      toast({
        title: "注册成功",
        description: "请登录",
        status: "success",
        duration: 3000,
        isClosable: true,
        position: "top",
      })
      window.location.href = "/login"
    } catch (error) {
      toast({
        title: "注册失败",
        description: error instanceof Error ? error.message : "请检查邀请码是否有效",
        status: "error",
        duration: 3000,
        isClosable: true,
        position: "top",
      })
    }
  }

  return (
    <Container maxW="md" py={12}>
      <VStack spacing={8}>
        <Heading size="xl">注册账号</Heading>
        <Box w="100%" as="form" onSubmit={handleSubmit(onSubmit)}>
          <Stack spacing={4}>
            <FormControl isInvalid={!!errors.email}>
              <FormLabel>邮箱地址</FormLabel>
              <Input
                type="email"
                {...register("email", {
                  required: "请输入邮箱地址",
                  pattern: {
                    value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                    message: "邮箱格式不正确",
                  },
                })}
                placeholder="your@email.com"
              />
              <FormErrorMessage>{errors.email?.message}</FormErrorMessage>
            </FormControl>

            <FormControl isInvalid={!!errors.password}>
              <FormLabel>密码</FormLabel>
              <Input
                type="password"
                {...register("password", {
                  required: "请输入密码",
                  minLength: {
                    value: 8,
                    message: "密码至少8个字符",
                  },
                })}
                placeholder="********"
              />
              <FormErrorMessage>{errors.password?.message}</FormErrorMessage>
            </FormControl>

            <FormControl isInvalid={!!errors.confirmPassword}>
              <FormLabel>确认密码</FormLabel>
              <Input
                type="password"
                {...register("confirmPassword", {
                  required: "请确认密码",
                  validate: (value) =>
                    value === password || "两次输入的密码不一致",
                })}
                placeholder="********"
              />
              <FormErrorMessage>{errors.confirmPassword?.message}</FormErrorMessage>
            </FormControl>

            <FormControl isInvalid={!!errors.inviteCode}>
              <FormLabel>邀请码</FormLabel>
              <Input
                {...register("inviteCode", {
                  required: "请输入邀请码",
                })}
                placeholder="请输入邀请码"
              />
              <FormErrorMessage>{errors.inviteCode?.message}</FormErrorMessage>
            </FormControl>

            <Button
              type="submit"
              colorScheme="blue"
              size="lg"
              isLoading={signUpMutation.isPending}
              loadingText="注册中..."
            >
              注册
            </Button>

            <Text textAlign="center" color="gray.600">
              已有账号？{" "}
              <Link to="/login" className="text-blue-500 hover:underline">
                立即登录
              </Link>
            </Text>
          </Stack>
        </Box>
      </VStack>
    </Container>
  )
} 