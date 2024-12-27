import {
  Button,
  Container,
  Flex,
  FormControl,
  FormErrorMessage,
  FormLabel,
  Input,
  Link,
  Text,
} from "@chakra-ui/react"
import { Link as RouterLink } from "@tanstack/react-router"
import { type SubmitHandler, useForm } from "react-hook-form"
import React from 'react'

import useAuth from "../../hooks/useAuth"
import { confirmPasswordRules, emailPattern, passwordRules } from "../../utils"

interface RegisterForm {
  email: string
  password: string
  confirm_password: string
  invite_code: string
}

export const Register = () => {
  const { signUpMutation } = useAuth()
  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors, isSubmitting },
  } = useForm<RegisterForm>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      email: "",
      password: "",
      confirm_password: "",
      invite_code: "",
    },
  })

  const onSubmit: SubmitHandler<RegisterForm> = (data) => {
    signUpMutation.mutate(data)
  }

  return (
    <Flex flexDir={{ base: "column", md: "row" }} justify="center" h="100vh">
      <Container
        as="form"
        onSubmit={handleSubmit(onSubmit)}
        h="100vh"
        maxW="sm"
        alignItems="stretch"
        justifyContent="center"
        gap={4}
        centerContent
      >
        <FormControl id="email" isInvalid={!!errors.email}>
          <FormLabel htmlFor="email" srOnly>
            邮箱
          </FormLabel>
          <Input
            id="email"
            {...register("email", {
              required: "请输入邮箱",
              pattern: emailPattern,
            })}
            placeholder="请输入邮箱"
            type="email"
          />
          {errors.email && (
            <FormErrorMessage>{errors.email.message}</FormErrorMessage>
          )}
        </FormControl>

        <FormControl id="password" isInvalid={!!errors.password}>
          <FormLabel htmlFor="password" srOnly>
            密码
          </FormLabel>
          <Input
            id="password"
            {...register("password", passwordRules())}
            placeholder="请输入密码"
            type="password"
          />
          {errors.password && (
            <FormErrorMessage>{errors.password.message}</FormErrorMessage>
          )}
        </FormControl>

        <FormControl id="confirm_password" isInvalid={!!errors.confirm_password}>
          <FormLabel htmlFor="confirm_password" srOnly>
            确认密码
          </FormLabel>
          <Input
            id="confirm_password"
            {...register("confirm_password", confirmPasswordRules(getValues))}
            placeholder="请确认密码"
            type="password"
          />
          {errors.confirm_password && (
            <FormErrorMessage>{errors.confirm_password.message}</FormErrorMessage>
          )}
        </FormControl>

        <FormControl id="invite_code" isInvalid={!!errors.invite_code}>
          <FormLabel htmlFor="invite_code" srOnly>
            邀请码
          </FormLabel>
          <Input
            id="invite_code"
            {...register("invite_code", {
              required: "请输入邀请码",
            })}
            placeholder="请输入邀请码"
            type="text"
          />
          {errors.invite_code && (
            <FormErrorMessage>{errors.invite_code.message}</FormErrorMessage>
          )}
        </FormControl>

        <Button
          variant="primary"
          type="submit"
          isLoading={isSubmitting}
          w="100%"
        >
          注册
        </Button>

        <Text textAlign="center">
          已有账号？{" "}
          <Link as={RouterLink} to="/login" color="blue.500">
            立即登录
          </Link>
        </Text>
      </Container>
    </Flex>
  )
}

export default Register
